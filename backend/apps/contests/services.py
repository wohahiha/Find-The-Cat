from __future__ import annotations

import secrets
from typing import Optional

from datetime import datetime

from django.utils import timezone
from django.conf import settings

from apps.common.base.base_service import BaseService
from apps.common.exceptions import (
    ValidationError,
    NotFoundError,
    ConflictError,
    PermissionDeniedError,
)
from django.db import transaction
from apps.accounts.models import User
from apps.challenges.models import ChallengeSolve
from apps.challenges.repo import (
    ChallengeRepo,
    ChallengeSolveRepo,
    ChallengeHintUnlockRepo,
    ChallengeCategoryRepo,
)
from apps.challenges.serializers import serialize_challenge, serialize_category
from apps.submissions.repo import SubmissionRepo
from apps.common.infra import redis_client
from apps.common.utils.redis_keys import scoreboard_key
from apps.common.ws_utils import broadcast_contest, broadcast_notify
from apps.common.infra.logger import get_logger, logger_extra
from apps.notifications.services import fanout_notifications, build_dedup_key
from apps.notifications.models import Notification
from apps.accounts.models import User

from .models import Contest, Team, TeamMember, ContestAnnouncement, ContestParticipant
from .repo import (
    ContestRepo,
    TeamRepo,
    TeamMemberRepo,
    ContestAnnouncementRepo,
    ContestParticipantRepo,
)
from .schemas import (
    ContestCreateSchema,
    TeamCreateSchema,
    TeamJoinSchema,
    TeamLeaveSchema,
    TeamDisbandSchema,
    AnnouncementCreateSchema,
    TeamInviteResetSchema,
    TeamTransferSchema,
    ContestCategoryUpdateSchema,
    ContestUpdateSchema,
)

# 服务层：实现比赛、公告、队伍的业务流程，依赖仓储与 Schema 校验

logger = get_logger(__name__)


def _get_id(obj):
    """安全获取对象 id，避免静态分析器误报"""
    return getattr(obj, "id", None)


def determine_contest_status(contest: Contest, *, now: datetime | None = None) -> str:
    """
    计算比赛当前状态：
    - 未开始：当前时间早于开始时间
    - 进行中：已开赛且未结束
    - 已结束：当前时间晚于结束时间
    """
    reference = now or timezone.now()
    if reference < contest.start_time:
        return "未开始"
    if reference <= contest.end_time:
        return "进行中"
    return "已结束"


def serialize_contest(
        contest: Contest,
        *,
        categories: list | None = None,
) -> dict:
    """比赛序列化：提供比赛基础信息与状态，用于 API 返回"""
    data = {
        "id": getattr(contest, "id", None),
        "name": contest.name,
        "slug": contest.slug,
        "description": contest.description,
        "visibility": contest.visibility,
        "start_time": contest.start_time,
        "end_time": contest.end_time,
        "freeze_time": contest.freeze_time,
        "registration_start_time": contest.registration_start_time,
        "registration_end_time": contest.registration_end_time,
        "is_team_based": contest.is_team_based,
        "max_team_members": contest.max_team_members,
        "is_active": contest.is_active,
        "status": determine_contest_status(contest),
    }
    if categories is not None:
        data["categories"] = [serialize_category(cat) for cat in categories]
    return data


def serialize_announcement(announcement: ContestAnnouncement) -> dict:
    """公告序列化：返回基础信息与时间戳"""
    return {
        "id": getattr(announcement, "id", None),
        "contest": getattr(announcement.contest, "slug", None),
        "title": announcement.title,
        "summary": announcement.summary,
        "content": announcement.content,
        "is_active": announcement.is_active,
        "created_at": announcement.created_at,
        "updated_at": announcement.updated_at,
    }


def serialize_team(team: Team) -> dict:
    """队伍序列化：包含队长、邀请码、成员数量等"""
    member_count = getattr(team, "active_member_count", None)
    if member_count is None:
        member_count = team.member_count
    payload = {
        "id": getattr(team, "id", None),
        "contest": getattr(team.contest, "slug", None),
        "name": team.name,
        "slug": team.slug,
        "description": team.description,
        "captain_id": getattr(team, "captain_id", None),
        "invite_token": team.invite_token,
        "member_count": member_count,
        "is_active": team.is_active,
    }
    members = getattr(team, "members_cache", None) or getattr(team, "members_prefetched", None)
    if members is None:
        # 避免大量查询，只有在极少数（如我的队伍）场景下读取成员
        try:
            members = list(team.members.filter(is_active=True).select_related("user"))
        except Exception:
            members = []
    if members:
        payload["members"] = [
            {
                "id": getattr(m, "user_id", None),
                "username": getattr(getattr(m, "user", None), "username", None),
                "joined_at": getattr(m, "joined_at", None),
                "role": getattr(m, "role", None),
            }
            for m in members
        ]
    return payload


class ContestContextService(BaseService[Contest]):
    """
    提供统一的比赛上下文（状态校验、成员关系等）
    """

    def __init__(
            self,
            contest_repo: ContestRepo | None = None,
            member_repo: TeamMemberRepo | None = None,
            team_repo: TeamRepo | None = None,
            participant_repo: ContestParticipantRepo | None = None,
    ):
        """注入比赛、成员、队伍仓储，方便在上下文校验中复用"""
        # 仓储依赖注入：默认使用实际仓储，便于测试时替换
        self.contest_repo = contest_repo or ContestRepo()
        self.member_repo = member_repo or TeamMemberRepo()
        self.team_repo = team_repo or TeamRepo()
        # 公告仓储：用于列表查询
        self.announcement_repo = ContestAnnouncementRepo()
        self.category_repo = ChallengeCategoryRepo()
        self.participant_repo = participant_repo or ContestParticipantRepo()

    def get_contest(self, slug: str) -> Contest:
        """根据 slug 获取比赛对象"""
        return self.contest_repo.get_by_slug(slug)

    @staticmethod
    def ensure_contest_started(contest: Contest) -> None:
        """校验比赛已开赛，否则抛业务校验错误"""
        if not contest.has_started:
            raise ValidationError(message="比赛尚未开始")

    @staticmethod
    def ensure_contest_not_ended(contest: Contest) -> None:
        """校验比赛未结束"""
        if contest.has_ended:
            raise ValidationError(message="比赛已结束")

    def ensure_contest_running(self, contest: Contest) -> None:
        """组合校验：比赛已开始且未结束"""
        self.ensure_contest_started(contest)
        self.ensure_contest_not_ended(contest)

    def ensure_contest_visible(self, contest: Contest, user: User) -> None:
        """
        校验比赛可见性：
        - 公开比赛直接放行
        - 私有比赛需登录且是管理员或已报名/加入队伍的选手
        """
        if contest.visibility == Contest.Visibility.PUBLIC:
            return
        if getattr(user, "is_staff", False):
            return
        if not getattr(user, "is_authenticated", False):
            raise PermissionDeniedError(message="比赛未公开，需登录访问")
        if not self.participant_repo.filter(contest=contest, user=user, is_valid=True).exists():
            raise PermissionDeniedError(message="比赛未公开，暂无访问权限")

    def get_user_membership(self, contest: Contest, user: User):
        """查询用户在比赛中的队伍关系"""
        return self.member_repo.get_membership(contest=contest, user=user)

    def get_user_team(self, contest: Contest, user: User) -> Optional[Team]:
        """获取用户所在队伍，若无则返回 None"""
        membership = self.get_user_membership(contest=contest, user=user)
        return membership.team if membership else None

    def mark_participation(self, contest: Contest, user: User, *,
                           allow_create: bool = False) -> ContestParticipant | None:
        """记录用户在比赛中的参与状态，用于后台筛选与参赛选手列表"""
        if not user.is_authenticated or user.is_staff:
            return None
        status = ContestParticipant.Status.REGISTERED
        if contest.has_ended:
            status = ContestParticipant.Status.FINISHED
        elif contest.has_started:
            status = ContestParticipant.Status.RUNNING
        if allow_create:
            membership = self.member_repo.get_membership(contest=contest, user=user)
            return self.participant_repo.ensure_status(
                contest,
                user,
                status,
                is_valid=bool(membership) or not contest.is_team_based,
            )
        existing = self.participant_repo.filter(contest=contest, user=user).first()
        if not existing:
            return None
        membership = self.member_repo.get_membership(contest=contest, user=user)
        return self.participant_repo.ensure_status(
            contest,
            user,
            status,
            is_valid=bool(membership) or not contest.is_team_based,
        )

    def ensure_registered(self, contest: Contest, user: User) -> ContestParticipant:
        """显式报名：创建或更新报名状态"""
        if user.is_staff:
            raise PermissionDeniedError(message="管理员不能报名参赛")
        if contest.has_ended:
            raise ConflictError(message="比赛已结束，无法报名")
        now = timezone.now()
        reg_start = getattr(contest, "registration_start_time", None)
        reg_end = getattr(contest, "registration_end_time", None) or contest.end_time
        if reg_start and now < reg_start:
            raise ConflictError(message="报名尚未开始")
        if reg_end and now > reg_end:
            raise ConflictError(message="报名已截止")
        status = ContestParticipant.Status.RUNNING if contest.has_started else ContestParticipant.Status.REGISTERED
        membership = self.member_repo.get_membership(contest=contest, user=user)
        is_valid = bool(membership) or not contest.is_team_based
        return self.participant_repo.ensure_status(contest, user, status, is_valid=is_valid)

    @staticmethod
    def _compute_user_badge(
            contest: Contest,
            *,
            participant: ContestParticipant | None = None,
            membership: TeamMember | None = None,
    ) -> str:
        """根据比赛与当前用户的报名/组队情况生成副状态标识"""
        now = timezone.now()
        registered = participant is not None
        reg_end = contest.registration_end_time or contest.start_time
        start = contest.start_time
        end = contest.end_time
        freeze = contest.freeze_time
        team_missing = contest.is_team_based and membership is None

        if not registered:
            # 未报名场景：区分报名是否已截止
            if reg_end and start and now > reg_end and now < start:
                return "registration_closed"
            return "unregistered"

        if reg_end and start and now > reg_end and now < start and not registered:
            return "registration_closed"
        if registered and team_missing and reg_end and now > reg_end:
            return "registration_invalid"
        if registered and team_missing and start and now < start:
            return "team_missing"
        if registered and freeze and now >= freeze and (end is None or now <= end):
            return "frozen"
        if registered and end and now > end:
            return "finished"
        if registered:
            return "registered"
        return ""

    def build_user_contest_fields(
            self,
            contest: Contest,
            *,
            participant: ContestParticipant | None = None,
            membership: TeamMember | None = None,
    ) -> dict:
        """统一构造与用户相关的比赛附加字段，便于列表与详情复用"""
        registered = participant is not None
        registration_valid = bool(participant.is_valid) if participant is not None else False
        team = membership.team if membership else None
        badge = self._compute_user_badge(contest, participant=participant, membership=membership)
        return {
            "registration_status": registered,
            "registration_valid": registration_valid,
            "my_team_id": getattr(team, "id", None),
            "my_team_name": getattr(team, "name", None),
            "user_badge": badge,
        }

    def perform(self, *args, **kwargs) -> Contest:
        """ContextService 不提供通用执行入口，防止误用 execute"""
        raise NotImplementedError("ContestContextService does not support execute()")

    def list_announcements(self, contest: Contest):
        """获取比赛公告列表（仅返回有效公告）"""
        return self.announcement_repo.list_active(contest)

    def list_categories(self, contest: Contest):
        """返回比赛下配置的题目分类"""
        return self.category_repo.list_by_contest(contest)


def serialize_team_member(member: TeamMember) -> dict:
    """队伍成员序列化：导出场景下附带用户基础标识"""
    user_id = getattr(member, "user_id", None)
    username = getattr(getattr(member, "user", None), "username", None) if user_id else None
    return {
        "user_id": user_id,
        "username": username,
        "role": member.role,
        "is_active": member.is_active,
        "joined_at": member.joined_at,
    }


def build_team_member_snapshot(member_repo: TeamMemberRepo, team: Team, *, limit: int = 20) -> dict:
    """构造队伍成员快照：包含成员列表与总人数，便于 WebSocket 推送"""
    active_members = list(member_repo.active_members(team)[:limit])
    member_count = team.member_count
    return {
        "member_count": member_count,
        "members": [serialize_team_member(m) for m in active_members],
        "has_more_members": member_count > len(active_members),
    }


class CreateContestService(BaseService[Contest]):
    """创建比赛：封装仓储写入与 Schema 转换"""

    def __init__(self, repo: ContestRepo | None = None, category_repo: ChallengeCategoryRepo | None = None):
        """允许外部传入自定义仓储，默认使用实际仓储"""
        self.repo = repo or ContestRepo()
        self.category_repo = category_repo or ChallengeCategoryRepo()

    def perform(self, schema: ContestCreateSchema) -> Contest:
        """将校验后的比赛入参写入数据库，生成新的比赛记录"""
        # 将 Schema 转为字典，去除无关字段后落库
        data = schema.to_dict(exclude_none=True)
        data.pop("contest_slug", None)
        categories = data.pop("categories", [])
        contest = self.repo.create(data)
        if categories:
            self.category_repo.sync_for_contest(contest=contest, categories=categories)
        logger.info("创建比赛", extra=logger_extra({"contest": contest.slug}))
        # 系统通知：新比赛发布
        users = list(User.objects.filter(is_active=True, is_staff=False))
        if users:
            dedup = build_dedup_key(type=Notification.Type.CONTEST_NEW, contest=contest)
            fanout_notifications(
                users,
                type=Notification.Type.CONTEST_NEW,
                title=f"新比赛发布：{contest.name}",
                body=f"开赛时间：{contest.start_time}",
                payload={"contest": contest.slug},
                contest=contest,
                dedup_key=dedup,
            )
        return contest


class ContestUpdateService(BaseService[Contest]):
    """更新比赛：支持部分字段编辑，校验时间与人数约束"""

    def __init__(self, repo: ContestRepo | None = None):
        self.repo = repo or ContestRepo()

    @transaction.atomic
    def perform(self, schema: ContestUpdateSchema) -> Contest:
        contest = self.repo.get_by_slug(schema.contest_slug)
        if contest.has_ended:
            raise ConflictError(message="比赛已结束，无法修改")
        now = timezone.now()

        def ensure_dt(value: datetime | str | None) -> datetime:
            # 将字符串或 naive datetime 统一转换为时区感知的 datetime
            if value is None:
                raise ValidationError(message="时间字段不能为空")
            if isinstance(value, str):
                dt = datetime.fromisoformat(value)
            else:
                dt = value
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, timezone.get_default_timezone())
            return dt

        # 计算更新后的时间窗口用于校验
        start_time = ensure_dt(schema.start_time) if schema.start_time is not None else contest.start_time
        end_time = ensure_dt(schema.end_time) if schema.end_time is not None else contest.end_time
        freeze_time = (
            ensure_dt(schema.freeze_time)
            if schema.freeze_time is not None
            else contest.freeze_time
        )
        reg_start_time = (
            ensure_dt(schema.registration_start_time)
            if schema.registration_start_time is not None
            else contest.registration_start_time
        )
        reg_end_time = (
            ensure_dt(schema.registration_end_time)
            if schema.registration_end_time is not None
            else contest.registration_end_time
        )
        if end_time <= start_time:
            raise ValidationError(message="结束时间必须晚于开始时间")
        if freeze_time and not (start_time <= freeze_time <= end_time):
            raise ValidationError(message="封榜时间必须介于比赛时间范围内")
        if reg_start_time and reg_end_time and reg_start_time > reg_end_time:
            raise ValidationError(message="报名开始时间需早于报名截止时间")
        if reg_start_time and reg_start_time > end_time:
            raise ValidationError(message="报名开始时间不能晚于比赛结束时间")
        if reg_end_time and reg_end_time > end_time:
            raise ValidationError(message="报名截止时间不能晚于比赛结束时间")

        # 报名开始时间：一经设置不可修改（允许从空 -> 设置一次）
        if schema.registration_start_time is not None:
            desired_reg_start = reg_start_time
            if contest.registration_start_time and desired_reg_start != contest.registration_start_time:
                raise ConflictError(message="报名开始时间设置后不可修改，如需调整请联系管理员重置比赛")

        # 报名时间调整仅允许在报名未截止前进行
        if (
                (schema.registration_start_time is not None or schema.registration_end_time is not None)
                and contest.registration_end_time
                and now > contest.registration_end_time
        ):
            raise ConflictError(message="报名已截止，无法调整报名时间")

        # 不允许把报名截止时间设置到当前时间之前（如需立即截止应使用专门操作）
        if schema.registration_end_time is not None and reg_end_time and reg_end_time < now:
            raise ConflictError(message="报名截止时间不能早于当前时间，如需提前截止请设置为当前时间或更晚")

        update_payload = schema.to_dict(exclude_none=True)
        update_payload.pop("contest_slug", None)
        # 时间字段使用上方规范化结果，避免字符串直接落库
        if schema.start_time is not None:
            update_payload["start_time"] = start_time
        if schema.end_time is not None:
            update_payload["end_time"] = end_time
        if schema.freeze_time is not None:
            update_payload["freeze_time"] = freeze_time
        if schema.registration_start_time is not None:
            update_payload["registration_start_time"] = reg_start_time
        if schema.registration_end_time is not None:
            update_payload["registration_end_time"] = reg_end_time
        contest = self.repo.update(contest, update_payload)
        logger.info(
            "更新比赛",
            extra=logger_extra({"contest": contest.slug}),
        )
        return contest


class ContestAnnouncementService(BaseService[ContestAnnouncement]):
    """
    管理比赛公告的服务：创建公告并返回记录
    """

    def __init__(
            self,
            contest_repo: ContestRepo | None = None,
            announcement_repo: ContestAnnouncementRepo | None = None,
            participant_repo: ContestParticipantRepo | None = None,
    ):
        """注入比赛与公告仓储，便于单元测试替换"""
        # 比赛仓储：根据 slug 拉取比赛
        self.contest_repo = contest_repo or ContestRepo()
        # 公告仓储：持久化公告内容
        self.announcement_repo = announcement_repo or ContestAnnouncementRepo()
        self.participant_repo = participant_repo or ContestParticipantRepo()

    def perform(self, schema: AnnouncementCreateSchema) -> ContestAnnouncement:
        """根据比赛标识创建公告，保持公告与比赛的关联关系"""
        contest = self.contest_repo.get_by_slug(schema.contest_slug)
        payload = schema.to_dict(exclude_none=True)
        payload.pop("contest_slug", None)
        payload["contest"] = contest
        announcement = self.announcement_repo.create(payload)
        logger.info(
            "创建比赛公告",
            extra=logger_extra({"contest": contest.slug, "announcement": getattr(announcement, "id", None)}),
        )
        # WebSocket 广播公告发布
        broadcast_contest(
            contest.slug,
            {
                "event": "announcement_published",
                "contest": contest.slug,
                "announcement_id": getattr(announcement, "id", None),
                "title": announcement.title,
            },
        )
        # 系统通知：推送给报名有效的参赛选手
        participants = list(self.participant_repo.filter(contest=contest, is_valid=True).select_related("user"))
        if participants:
            dedup = build_dedup_key(
                type=Notification.Type.CONTEST_ANNOUNCEMENT_NEW,
                contest=contest,
                extra=str(getattr(announcement, "id", None)),
            )
            users = [p.user for p in participants if getattr(p, "user", None)]
            fanout_notifications(
                users,
                type=Notification.Type.CONTEST_ANNOUNCEMENT_NEW,
                title=f"比赛公告：{announcement.title}",
                body=announcement.summary or announcement.title,
                payload={
                    "contest": contest.slug,
                    "announcement_id": getattr(announcement, "id", None),
                },
                contest=contest,
                dedup_key=dedup,
            )
        return announcement


class ContestCategoryUpdateService(BaseService[list]):
    """
    比赛题目分类更新服务：同步比赛下的分类集合
    """

    def __init__(
            self,
            contest_repo: ContestRepo | None = None,
            category_repo: ChallengeCategoryRepo | None = None,
    ):
        self.contest_repo = contest_repo or ContestRepo()
        self.category_repo = category_repo or ChallengeCategoryRepo()

    def perform(self, schema: ContestCategoryUpdateSchema) -> list:
        contest = self.contest_repo.get_by_slug(schema.contest_slug)
        categories = self.category_repo.sync_for_contest(contest=contest, categories=schema.categories or [])
        return categories


class TeamCreateService(BaseService[Team]):
    """
    创建队伍服务：
    - 校验用户角色与比赛状态
    - 自动创建队伍并将创建者设为队长成员
    """

    def __init__(
            self,
            contest_repo: ContestRepo | None = None,
            team_repo: TeamRepo | None = None,
            member_repo: TeamMemberRepo | None = None,
            participant_repo: ContestParticipantRepo | None = None,
    ):
        """注入比赛、队伍、成员仓储，便于不同环境下替换实现"""
        # 注入比赛、队伍、成员仓储，便于服务层统一调用
        self.contest_repo = contest_repo or ContestRepo()
        self.team_repo = team_repo or TeamRepo()
        self.member_repo = member_repo or TeamMemberRepo()
        self.participant_repo = participant_repo or ContestParticipantRepo()

    def perform(self, user: User, schema: TeamCreateSchema) -> Team:
        """以当前用户为队长创建队伍，完成唯一 slug 与成员记录写入"""
        # 1) 获取比赛并校验管理员不可参赛、比赛允许组队、未结束
        contest = self.contest_repo.get_by_slug(schema.contest_slug)
        if user.is_staff:
            raise ValidationError(message="管理员账号无法参与比赛")
        if not contest.is_team_based:
            raise ValidationError(message="该比赛不支持组队")
        if contest.has_ended:
            raise ConflictError(message="比赛已结束，无法创建队伍")
        # 0) 报名校验：需先显式报名
        if not self.participant_repo.filter(contest=contest, user=user).exists():
            raise ValidationError(message="请先报名参赛后再创建队伍")
        # 2) 校验用户尚未加入该比赛的任何队伍
        existing = self.member_repo.get_membership(contest=contest, user=user)
        if existing:
            raise ConflictError(message="您已加入该比赛的队伍")
        # 3) 创建队伍并写入队长成员记录
        user_id = getattr(user, "id", None)
        team = self.team_repo.create_team(
            contest=contest,
            captain=user,
            name=schema.name,
            description=schema.description,
        )
        captain_member = self.member_repo.create_member(team=team, user=user, role=TeamMember.Role.CAPTAIN)
        self.participant_repo.ensure_status(
            contest,
            user,
            ContestParticipant.Status.RUNNING if contest.has_started else ContestParticipant.Status.REGISTERED,
            is_valid=True,
        )
        team_id = getattr(team, "id", None)
        logger.info(
            "创建队伍",
            extra=logger_extra({"contest": contest.slug, "team": team.slug, "user_id": user_id}),
        )
        snapshot = build_team_member_snapshot(self.member_repo, team, limit=20)
        captain_payload = serialize_team_member(captain_member)
        broadcast_contest(
            contest.slug,
            {
                "event": "team_created",
                "contest": contest.slug,
                "team": team.slug,
                "team_id": team_id,
                "user_id": user_id,
                "member": captain_payload,
                **snapshot,
            },
        )
        broadcast_notify(
            user_id,
            {
                "event": "team_created",
                "contest": contest.slug,
                "team": team.slug,
                "team_id": team_id,
                "member": captain_payload,
                **snapshot,
            },
        )
        return team


class TeamJoinService(BaseService[TeamMember]):
    """
    加入队伍服务：
    - 校验邀请码有效、人数未满、用户未加入其他队伍、比赛未结束
    """

    def __init__(
            self,
            contest_repo: ContestRepo | None = None,
            team_repo: TeamRepo | None = None,
            member_repo: TeamMemberRepo | None = None,
            participant_repo: ContestParticipantRepo | None = None,
    ):
        """注入比赛、队伍、成员仓储，供加入校验与写入使用"""
        # 仓储依赖：用于查询比赛、队伍与成员关系
        self.contest_repo = contest_repo or ContestRepo()
        self.team_repo = team_repo or TeamRepo()
        self.member_repo = member_repo or TeamMemberRepo()
        self.participant_repo = participant_repo or ContestParticipantRepo()

    def perform(self, user: User, schema: TeamJoinSchema) -> TeamMember:
        """校验并将用户加入目标队伍，返回成员关系记录"""
        # 1) 获取比赛并禁止管理员加入
        contest = self.contest_repo.get_by_slug(schema.contest_slug)
        if user.is_staff:
            raise ValidationError(message="管理员账号无法加入队伍")
        if contest.has_ended:
            raise ConflictError(message="比赛已结束，无法加入队伍")
        # 报名校验：需先显式报名
        if not self.participant_repo.filter(contest=contest, user=user).exists():
            raise ValidationError(message="请先报名参赛后再加入队伍")
        # 2) 根据邀请码查找队伍
        team = (
            self.team_repo.filter(contest=contest, invite_token=schema.invite_token, is_active=True)
            .select_related("contest")
            .first()
        )
        if team is None:
            raise NotFoundError(message="邀请码无效")
        user_id = getattr(user, "id", None)
        team_id = getattr(team, "id", None)
        # 3) 校验人数上限、用户未在其他队伍、比赛未结束
        if team.member_count >= contest.max_team_members:
            logger.warning(
                "加入队伍失败：人数已满",
                extra=logger_extra({"contest": contest.slug, "team": team.slug, "user_id": user_id}),
            )
            raise ConflictError(message="队伍人数已满")
        if self.member_repo.get_membership(contest=contest, user=user):
            logger.warning(
                "加入队伍失败：已在队伍",
                extra=logger_extra({"contest": contest.slug, "user_id": user_id}),
            )
            raise ConflictError(message="您已经加入了一支队伍")
        if contest.has_ended:
            logger.warning(
                "加入队伍失败：比赛已结束",
                extra=logger_extra({"contest": contest.slug, "team": team.slug, "user_id": user_id}),
            )
            raise ConflictError(message="比赛已结束，无法加入队伍")
        member = self.member_repo.create_member(team=team, user=user, role=TeamMember.Role.MEMBER)
        self.participant_repo.ensure_status(
            contest,
            user,
            ContestParticipant.Status.RUNNING if contest.has_started else ContestParticipant.Status.REGISTERED,
            is_valid=True,
        )
        logger.info(
            "加入队伍",
            extra=logger_extra({"contest": contest.slug, "team": team.slug, "user_id": user_id}),
        )
        snapshot = build_team_member_snapshot(self.member_repo, team, limit=20)
        member_payload = serialize_team_member(member)
        broadcast_contest(
            contest.slug,
            {
                "event": "team_joined",
                "contest": contest.slug,
                "team": team.slug,
                "team_id": team_id,
                "user_id": user_id,
                "member": member_payload,
                **snapshot,
            },
        )
        broadcast_notify(
            user_id,
            {
                "event": "team_joined",
                "contest": contest.slug,
                "team": team.slug,
                "team_id": team_id,
                "member": member_payload,
                **snapshot,
            },
        )
        # 系统通知：队员加入队伍
        members = list(self.member_repo.active_members(team))
        if members:
            dedup = build_dedup_key(
                type=Notification.Type.TEAM_MEMBER_JOINED,
                contest=contest,
                team=team,
                extra=str(user_id),
            )
            fanout_notifications(
                [m.user for m in members if getattr(m, "user", None)],
                type=Notification.Type.TEAM_MEMBER_JOINED,
                title=f"{getattr(user, 'username', '成员')} 加入队伍",
                body=team.name,
                payload={
                    "contest": contest.slug,
                    "team": team.slug,
                    "team_id": team_id,
                    "user_id": user_id,
                },
                contest=contest,
                team=team,
                dedup_key=dedup,
            )
        return member


class ContestRegisterService(BaseService[ContestParticipant]):
    """显式报名服务：供前台“报名参赛”按钮调用"""

    def __init__(self, context_service: ContestContextService | None = None):
        self.context_service = context_service or ContestContextService()

    def perform(self, user: User, contest_slug: str) -> ContestParticipant:
        contest = self.context_service.get_contest(contest_slug)
        return self.context_service.ensure_registered(contest, user)


class TeamLeaveService(BaseService[None]):
    """
    退出队伍服务：
    - 校验用户是否在队伍中
    - 队长需先解散或移交后才能退出
    """

    def __init__(
            self,
            contest_repo: ContestRepo | None = None,
            member_repo: TeamMemberRepo | None = None,
    ):
        """注入比赛与成员仓储，便于读取当前成员关系"""
        # 仓储依赖：用于校验比赛与当前成员关系
        self.contest_repo = contest_repo or ContestRepo()
        self.member_repo = member_repo or TeamMemberRepo()

    def perform(self, user: User, schema: TeamLeaveSchema) -> None:
        """处理成员退出队伍，队长且多人时阻止直接退出"""
        # 1) 获取比赛与当前成员关系
        contest = self.contest_repo.get_by_slug(schema.contest_slug)
        membership = self.member_repo.get_membership(contest=contest, user=user)
        if not membership:
            raise NotFoundError(message="你尚未加入任何队伍")
        user_id = getattr(user, "id", None)
        # 2) 队长且队伍多人时禁止直接退出
        if membership.role == TeamMember.Role.CAPTAIN:
            team = membership.team
            if team.member_count > 1:
                logger.warning(
                    "退出队伍失败：队长且队伍多人",
                    extra=logger_extra({"contest": contest.slug, "team": team.slug, "user_id": user_id}),
                )
                raise ConflictError(message="队长请先将队伍解散或移交队长后再退出")
        # 3) 标记成员无效
        member_payload = serialize_team_member(membership)
        self.member_repo.remove_member(membership)
        logger.info(
            "退出队伍",
            extra=logger_extra({"contest": contest.slug, "team": membership.team.slug, "user_id": user_id}),
        )
        snapshot = build_team_member_snapshot(self.member_repo, membership.team, limit=20)
        team_id = getattr(membership.team, "id", None)
        broadcast_contest(
            contest.slug,
            {
                "event": "team_left",
                "contest": contest.slug,
                "team": membership.team.slug,
                "team_id": team_id,
                "user_id": user_id,
                "member": member_payload,
                **snapshot,
            },
        )
        broadcast_notify(
            user_id,
            {
                "event": "team_left",
                "contest": contest.slug,
                "team": membership.team.slug,
                "team_id": team_id,
                "member": member_payload,
                **snapshot,
            },
        )
        members = list(self.member_repo.active_members(membership.team))
        if members:
            dedup = build_dedup_key(
                type=Notification.Type.TEAM_MEMBER_LEFT,
                contest=contest,
                team=membership.team,
                extra=str(user_id),
            )
            fanout_notifications(
                [m.user for m in members if getattr(m, "user", None)],
                type=Notification.Type.TEAM_MEMBER_LEFT,
                title=f"{getattr(user, 'username', '成员')} 退出队伍",
                body=membership.team.name,
                payload={
                    "contest": contest.slug,
                    "team": membership.team.slug,
                    "team_id": team_id,
                    "user_id": user_id,
                },
                contest=contest,
                team=membership.team,
                dedup_key=dedup,
            )


class TeamDisbandService(BaseService[Team]):
    """
    解散队伍服务：
    - 队长或管理员可操作
    - 逐个成员失效并关闭队伍
    """

    def __init__(
            self,
            team_repo: TeamRepo | None = None,
            member_repo: TeamMemberRepo | None = None,
    ):
        """注入队伍与成员仓储，便于批量标记成员失效"""
        # 仓储依赖：队伍与成员查询/更新
        self.team_repo = team_repo or TeamRepo()
        self.member_repo = member_repo or TeamMemberRepo()

    def perform(self, user: User, schema: TeamDisbandSchema) -> Team:
        """解散目标队伍，逐个成员失效并关闭队伍记录"""
        # 1) 校验权限：仅队长或管理员
        team = self.team_repo.get_by_id(schema.team_id)
        user_id = getattr(user, "id", None)
        if not (user.is_staff or getattr(team, "captain_id", None) == user_id):
            raise PermissionDeniedError(message="只有队长或管理员可以解散队伍")
        member_objs = list(self.member_repo.active_members(team))
        members_before = [serialize_team_member(m) for m in member_objs]
        # 2) 标记所有成员失效
        for member in self.member_repo.active_members(team):
            member.is_active = False
            member.save(update_fields=["is_active"])
        # 3) 关闭队伍并重置邀请码，避免复用
        team.is_active = False
        team.invite_token = secrets.token_hex(4)
        team.save(update_fields=["is_active", "invite_token", "updated_at"])
        logger.info(
            "解散队伍",
            extra=logger_extra({"team": team.slug, "contest": getattr(team.contest, 'slug', None),
                                "user_id": user_id}),
        )
        team_id = getattr(team, "id", None)
        broadcast_contest(
            getattr(team.contest, "slug", ""),
            {
                "event": "team_disbanded",
                "contest": getattr(team.contest, "slug", None),
                "team": team.slug,
                "team_id": team_id,
                "members": members_before,
                "member_count": len(members_before),
            },
        )
        if member_objs:
            dedup = build_dedup_key(
                type=Notification.Type.TEAM_DISBANDED,
                contest=getattr(team, "contest", None),
                team=team,
                extra=str(team_id),
            )
            fanout_notifications(
                [m.user for m in member_objs if getattr(m, "user", None)],
                type=Notification.Type.TEAM_DISBANDED,
                title="队伍已解散",
                body=team.name,
                payload={
                    "contest": getattr(team.contest, "slug", None),
                    "team": team.slug,
                    "team_id": team_id,
                },
                contest=getattr(team, "contest", None),
                team=team,
                dedup_key=dedup,
            )
        return team


class TeamInviteResetService(BaseService[Team]):
    """重置队伍邀请码：仅队长或管理员可操作"""

    def __init__(self, team_repo: TeamRepo | None = None, member_repo: TeamMemberRepo | None = None):
        """允许注入自定义队伍仓储以便测试或替换实现"""
        # 队伍仓储：用于重置邀请码时读取与更新队伍
        self.team_repo = team_repo or TeamRepo()
        self.member_repo = member_repo or TeamMemberRepo()

    def perform(self, user: User, schema: TeamInviteResetSchema) -> Team:
        """校验队伍有效性与操作者权限后重置邀请码"""
        team = self.team_repo.get_by_id(schema.team_id)
        if not team.is_active:
            raise ConflictError(message="队伍已失效，无法重置邀请码")
        user_id = getattr(user, "id", None)
        if not (user.is_staff or getattr(team, "captain_id", None) == user_id):
            raise PermissionDeniedError(message="仅队长或管理员可重置邀请码")
        # 使用随机 token 生成新邀请码
        token = secrets.token_hex(4)
        result = self.team_repo.reset_invite_token(team, token=token)
        logger.info(
            "重置队伍邀请码",
            extra=logger_extra({"team": team.slug, "contest": getattr(team.contest, 'slug', None),
                                "user_id": user_id}),
        )
        team_id = getattr(team, "id", None)
        broadcast_contest(
            getattr(team.contest, "slug", ""),
            {
                "event": "team_invite_reset",
                "contest": getattr(team.contest, "slug", None),
                "team": team.slug,
                "team_id": team_id,
                "invite_token": team.invite_token,
                "member_count": team.member_count,
            },
        )
        # 通知队伍成员邀请码重置
        members = list(self.member_repo.active_members(team))
        if members:
            dedup = build_dedup_key(
                type=Notification.Type.TEAM_INVITE_RESET,
                contest=getattr(team, "contest", None),
                team=team,
                extra=str(team.invite_token),
            )
            fanout_notifications(
                [m.user for m in members if getattr(m, "user", None)],
                type=Notification.Type.TEAM_INVITE_RESET,
                title="队伍邀请码已重置",
                body=f"{team.name} 的新邀请码：{team.invite_token}",
                payload={
                    "contest": getattr(team.contest, "slug", None),
                    "team": team.slug,
                    "team_id": team_id,
                    "invite_token": team.invite_token,
                },
                contest=getattr(team, "contest", None),
                team=team,
                dedup_key=dedup,
            )
        return result


class TeamTransferService(BaseService[Team]):
    """队长移交：将队长角色转给指定队员"""

    def __init__(
            self,
            team_repo: TeamRepo | None = None,
            member_repo: TeamMemberRepo | None = None,
    ):
        """注入队伍与成员仓储，支持扩展或测试替换"""
        # 仓储依赖：负责读取队伍状态与成员关系
        self.team_repo = team_repo or TeamRepo()
        self.member_repo = member_repo or TeamMemberRepo()

    @transaction.atomic
    def perform(self, user: User, schema: TeamTransferSchema) -> Team:
        """在事务内完成队长权限转移，确保成员关系与队长字段一致"""
        # 1) 校验队伍有效与操作者权限
        team = self.team_repo.get_by_id(schema.team_id)
        if not team.is_active:
            raise ConflictError(message="队伍已失效，无法移交队长")
        user_id = getattr(user, "id", None)
        if not (user.is_staff or getattr(team, "captain_id", None) == user_id):
            raise PermissionDeniedError(message="仅队长或管理员可移交队长")
        # 2) 查找或创建目标成员记录
        target_user = User.objects.filter(pk=schema.new_captain_id).first()
        if not target_user:
            raise NotFoundError(message="目标用户不存在")
        target_user_id = getattr(target_user, "id", None)
        membership = self.member_repo.filter(team=team, user_id=target_user_id).first()
        if membership is None:
            membership = self.member_repo.create_member(
                team=team,
                user=target_user,
                role=TeamMember.Role.MEMBER,
            )
        # 3) 确保成员有效
        if not membership.is_active:
            membership.is_active = True
            membership.save(update_fields=["is_active"])
        # 更新角色与队长
        old_captain_id = getattr(team, "captain_id", None)
        team.captain_id = target_user_id
        team.save(update_fields=["captain_id", "updated_at"])
        membership.role = TeamMember.Role.CAPTAIN
        membership.save(update_fields=["role"])
        self.member_repo.filter(team=team, user_id=old_captain_id).update(role=TeamMember.Role.MEMBER, is_active=True)
        snapshot = build_team_member_snapshot(self.member_repo, team, limit=20)
        new_captain_payload = serialize_team_member(membership)
        logger.info(
            "移交队长",
            extra=logger_extra(
                {"team": team.slug, "contest": getattr(team.contest, 'slug', None), "old_captain": old_captain_id,
                 "new_captain": target_user_id}
            ),
        )
        team_id = getattr(team, "id", None)
        broadcast_contest(
            getattr(team.contest, "slug", ""),
            {
                "event": "team_transferred",
                "contest": getattr(team.contest, "slug", None),
                "team": team.slug,
                "team_id": team_id,
                "old_captain": old_captain_id,
                "new_captain": target_user_id,
                "members": snapshot.get("members"),
                "member_count": snapshot.get("member_count"),
            },
        )
        broadcast_notify(
            target_user_id,
            {
                "event": "team_transferred",
                "contest": getattr(team.contest, "slug", None),
                "team": team.slug,
                "team_id": team_id,
                "member": new_captain_payload,
                **snapshot,
            },
        )
        # 通知全队队长变更
        members = list(self.member_repo.active_members(team))
        if members:
            dedup = build_dedup_key(
                type=Notification.Type.TEAM_CAPTAIN_TRANSFERRED,
                contest=getattr(team, "contest", None),
                team=team,
                extra=f"{old_captain_id}->{target_user_id}",
            )
            fanout_notifications(
                [m.user for m in members if getattr(m, "user", None)],
                type=Notification.Type.TEAM_CAPTAIN_TRANSFERRED,
                title="队长已变更",
                body=f"新队长：{getattr(target_user, 'username', target_user_id)}",
                payload={
                    "contest": getattr(team.contest, "slug", None),
                    "team": team.slug,
                    "team_id": team_id,
                    "old_captain": old_captain_id,
                    "new_captain": target_user_id,
                },
                contest=getattr(team, "contest", None),
                team=team,
                dedup_key=dedup,
            )
        return team


class ScoreboardService(BaseService[list[dict]]):
    """
    记分板服务：
    - 汇总比赛内的解题记录，按分数与时间排序生成排名
    - 支持 Redis 缓存以减轻重复计算开销
    """
    atomic_enabled = False
    cache_ttl_seconds: int = getattr(settings, "SCOREBOARD_CACHE_TTL", 30)

    def perform(self, contest: Contest, *, ignore_freeze: bool = False) -> list[dict]:
        """计算记分板：汇总解题记录并排序"""
        contest_id = getattr(contest, "id", None)
        cache_key = self.cache_key(contest_id, ignore_freeze=ignore_freeze)
        cached = redis_client.get_json(cache_key)
        if isinstance(cached, list):
            return cached

        # 1) 计算封榜/截止时间，封榜后只统计封榜前的解题；否则以比赛结束时间为上限
        now = timezone.now()
        cutoff = contest.end_time
        if contest.freeze_time and now >= contest.freeze_time and not ignore_freeze:
            cutoff = min(contest.freeze_time, contest.end_time)

        # 2) 查询满足时间窗口的解题，按时间排序（裁剪字段，减少 IO）
        solve_rows = (
            ChallengeSolve.objects.filter(challenge__contest=contest, solved_at__lte=cutoff)
            .select_related("challenge", "team", "user")
            .values(
                "challenge__slug",
                "team_id",
                "user_id",
                "awarded_points",
                "bonus_points",
                "solved_at",
                "team__slug",
                "team__name",
                "user__username",
            )
            .order_by("solved_at")
        )
        board: dict[str, dict] = {}
        for solve in solve_rows:
            # 组队赛必须绑定队伍，防止脏数据混入榜单
            if contest.is_team_based and not solve["team_id"]:
                logger.warning(
                    "跳过未绑定队伍的解题记录",
                    extra=logger_extra(
                        {
                            "contest": getattr(contest, "slug", None),
                            "challenge": solve.get("challenge__slug"),
                            "user_id": solve.get("user_id"),
                        }
                    ),
                )
                continue
            key: str
            entry: dict
            if contest.is_team_based and solve["team_id"]:
                # 组队赛：按队伍汇总
                key = f"team-{solve['team_id']}"
                entry = board.setdefault(
                    key,
                    {
                        "type": "team",
                        "team": {
                            "id": solve["team_id"],
                            "name": solve["team__name"],
                            "slug": solve["team__slug"],
                        },
                        "score": 0,
                        "bonus_score": 0,
                        "last_solve": solve["solved_at"],
                        "solves": [],
                    },
                )
            else:
                # 个人赛：按用户汇总
                key = f"user-{solve['user_id']}"
                entry = board.setdefault(
                    key,
                    {
                        "type": "user",
                        "user": {
                            "id": solve["user_id"],
                            "username": solve["user__username"],
                        },
                        "score": 0,
                        "bonus_score": 0,
                        "last_solve": solve["solved_at"],
                        "solves": [],
                    },
                )
            bonus_points = solve.get("bonus_points") or 0
            entry["score"] += solve["awarded_points"]
            entry["bonus_score"] += bonus_points
            entry["last_solve"] = solve["solved_at"]
            entry["solves"].append(
                {
                    "challenge": solve["challenge__slug"],
                    "points": solve["awarded_points"],
                    "bonus_points": bonus_points,
                    "base_points": solve["awarded_points"] - bonus_points,
                    "solved_at": solve["solved_at"],
                }
            )

        # 3) 依据分数与最后解题时间排序并生成排名
        sorted_entries = sorted(
            board.values(),
            key=lambda item: (-item["score"], item["last_solve"]),
        )
        result: list[dict] = []
        for idx, entry in enumerate(sorted_entries, start=1):
            solves_payload = []
            for solve in entry.get("solves", []):
                solved_at = solve.get("solved_at")
                solved_at_str = solved_at.isoformat() if hasattr(solved_at, "isoformat") else str(solved_at)
                solves_payload.append(
                    {
                        "challenge": solve.get("challenge"),
                        "points": solve.get("points"),
                        "bonus_points": solve.get("bonus_points", 0),
                        "base_points": solve.get("base_points"),
                        "solved_at": solved_at_str,
                    }
                )
            payload = {
                **{k: v for k, v in entry.items() if k not in {"solves", "last_solve"}},
                "rank": idx,
                "solves": solves_payload,
            }
            result.append(payload)
        redis_client.set_json(cache_key, result, ex=self.cache_ttl_seconds)
        return result

    @staticmethod
    def cache_key(contest_id: int, *, ignore_freeze: bool = False) -> str:
        # 生成记分板缓存键，便于缓存读写；后台忽略封榜时区分缓存键
        suffix = "admin" if ignore_freeze else "front"
        return f"{scoreboard_key(contest_id)}:{suffix}"

    @classmethod
    def invalidate_cache(cls, contest_id: int) -> None:
        # 主动失效记分板缓存，供提交/判题后调用
        redis_client.delete(cls.cache_key(contest_id))
        redis_client.delete(cls.cache_key(contest_id, ignore_freeze=True))

    def build_snapshot(
            self,
            contest: Contest,
            *,
            limit: int = 10,
            ignore_freeze: bool = False,
    ) -> dict:
        """
        构建推送用的榜单摘要：
        - 默认返回前 N 名，减少前端重复拉取
        - ignore_freeze 可用于后台忽略封榜
        """
        board = self.execute(contest, ignore_freeze=ignore_freeze)
        entries = board if not limit or limit <= 0 else board[:limit]
        return {
            "contest": contest.slug,
            "entries": entries,
            "top_limit": limit,
            "ignore_freeze": ignore_freeze,
            "generated_at": timezone.now().isoformat(),
        }


class ContestExportService(BaseService[dict]):
    """
    比赛数据导出服务：
    - 提供比赛基础信息、队伍成员、题目、解题记录与提交记录
    - 管理端使用，用于备份或运营分析
    """

    atomic_enabled = False

    def __init__(
            self,
            contest_repo: ContestRepo | None = None,
            team_repo: TeamRepo | None = None,
            member_repo: TeamMemberRepo | None = None,
            challenge_repo: ChallengeRepo | None = None,
            solve_repo: ChallengeSolveRepo | None = None,
            submission_repo: SubmissionRepo | None = None,
            scoreboard_service: ScoreboardService | None = None,
            hint_unlock_repo: ChallengeHintUnlockRepo | None = None,
            category_repo: ChallengeCategoryRepo | None = None,
    ):
        """集中注入比赛、队伍、成员、题目、解题、提交与榜单依赖"""
        # 仓储与服务依赖：集中注入，方便测试替换
        self.contest_repo = contest_repo or ContestRepo()
        self.team_repo = team_repo or TeamRepo()
        self.member_repo = member_repo or TeamMemberRepo()
        self.challenge_repo = challenge_repo or ChallengeRepo()
        self.solve_repo = solve_repo or ChallengeSolveRepo()
        self.submission_repo = submission_repo or SubmissionRepo()
        self.scoreboard_service = scoreboard_service or ScoreboardService()
        self.hint_unlock_repo = hint_unlock_repo or ChallengeHintUnlockRepo()
        self.category_repo = category_repo or ChallengeCategoryRepo()

    def perform(self, contest_slug: str) -> dict:
        """导出指定比赛的数据快照"""
        contest = self.contest_repo.get_by_slug(contest_slug)

        # 队伍与成员
        teams_payload = []
        teams = self.team_repo.filter(contest=contest).select_related("captain")
        members_qs = self.member_repo.filter(team__contest=contest).select_related("user", "team")
        members_by_team: dict[int, list[TeamMember]] = {}
        for member in members_qs:
            members_by_team.setdefault(getattr(member, "team_id", None), []).append(member)

        for team in teams:
            team_id = getattr(team, "id", None)
            payload = serialize_team(team)
            payload["members"] = [serialize_team_member(m) for m in members_by_team.get(team_id, [])]
            teams_payload.append(payload)

        # 题目列表
        challenges = (
            self.challenge_repo.filter(contest=contest)
            .select_related("category", "author")
            .prefetch_related("tasks", "attachments", "hints")
        )
        challenges_payload = [serialize_challenge(ch) for ch in challenges]

        # 解题记录（供榜单或统计使用）
        solves = (
            self.solve_repo.filter(challenge__contest=contest)
            .select_related("challenge", "user", "team")
            .order_by("solved_at")
        )
        solves_payload = [
            {
                "challenge": getattr(solve.challenge, "slug", None),
                "user": getattr(solve, "user_id", None),
                "username": solve.user.username if getattr(solve, "user_id", None) else None,
                "team": getattr(solve, "team_id", None),
                "awarded_points": getattr(solve, "awarded_points", 0),
                "bonus_points": getattr(solve, "bonus_points", 0),
                "solved_at": getattr(solve, "solved_at", None),
            }
            for solve in solves
        ]

        # 提交记录（包含正确/错误/重复）
        submissions = (
            self.submission_repo.filter(contest=contest)
            .select_related("challenge", "user", "team")
            .order_by("-created_at")
        )
        submissions_payload = [
            {
                "id": getattr(sub, "id", None),
                "contest": getattr(sub.contest, "slug", None),
                "challenge": getattr(sub.challenge, "slug", None),
                "user": getattr(sub, "user_id", None),
                "team": getattr(sub, "team_id", None),
                "status": sub.status,
                "is_correct": sub.is_correct,
                "awarded_points": getattr(sub, "awarded_points", 0),
                "bonus_points": getattr(sub, "bonus_points", 0),
                "blood_rank": getattr(sub, "blood_rank", None),
                "message": sub.message,
                "solve_id": getattr(sub, "solve_id", None),
                "created_at": getattr(sub, "created_at", None),
                "judged_at": getattr(sub, "judged_at", None),
            }
            for sub in submissions
        ]

        # 记分板快照（与详情页相同计算逻辑）
        scoreboard_payload = self.scoreboard_service.execute(contest)
        summary_payload = self._build_summary(contest, scoreboard_payload, solves_payload, submissions_payload)

        contest_categories = self.category_repo.list_by_contest(contest)
        challenge_stats = self._build_challenge_stats(challenges_payload, submissions_payload, solves_payload)
        return {
            "meta": serialize_contest(contest, categories=contest_categories),
            "overview": {
                "summary": summary_payload,
                "scoreboard": scoreboard_payload,
            },
            "challenges": challenge_stats,
            "extra": {
                "teams": teams_payload,
                "solves": solves_payload,
                "submissions": submissions_payload,
            },
        }

    @staticmethod
    def _build_summary(contest, scoreboard_payload, solves_payload, submissions_payload):
        """构建比赛总览：冠军队/个人、最佳个人贡献等"""
        _ = contest
        top_team = None
        top_user = None
        team_ranking: list[dict] = []
        individual_ranking: list[dict] = []

        # 从榜单直接生成队伍排名（团队赛时有值）
        for entry in scoreboard_payload:
            if entry.get("type") == "team":
                team_data = entry.get("team", {})
                team_ranking.append(
                    {
                        "rank": entry.get("rank"),
                        "team": team_data,
                        "score": entry.get("score"),
                        "bonus_score": entry.get("bonus_score"),
                        "solves": entry.get("solves"),
                    }
                )
            elif entry.get("type") == "user":
                individual_ranking.append(
                    {
                        "rank": entry.get("rank"),
                        "user": entry.get("user"),
                        "score": entry.get("score"),
                        "bonus_score": entry.get("bonus_score"),
                        "solves": entry.get("solves"),
                    }
                )
        if team_ranking:
            top_team = team_ranking[0].get("team")
        if individual_ranking:
            top_user = individual_ranking[0].get("user")

        # 个人贡献榜（保证团队赛也有个人榜）：统计 solves 和分数
        individual_scores: dict[int, dict] = {}
        for solve in solves_payload:
            user_id = solve.get("user")
            if not user_id:
                continue
            entry = individual_scores.setdefault(
                user_id,
                {
                    "user_id": user_id,
                    "username": solve.get("username"),
                    "score": 0,
                    "bonus_score": 0,
                    "solves": 0,
                },
            )
            entry["score"] += solve.get("awarded_points", 0)
            entry["bonus_score"] += solve.get("bonus_points", 0)
            entry["solves"] += 1
        # 如果榜单有用户字段，回填 username
        for entry in scoreboard_payload:
            if entry.get("type") == "user" and entry.get("user", {}).get("id"):
                uid = entry["user"]["id"]
                if uid in individual_scores:
                    individual_scores[uid]["username"] = entry["user"].get("username")

        if individual_scores:
            sorted_individuals = sorted(
                individual_scores.values(),
                key=lambda x: (-x["score"], -x["bonus_score"], -x["solves"]),
            )
            # 重新写回排名列表（团队赛也有个人榜）
            individual_ranking = [
                {**entry, "rank": idx + 1}
                for idx, entry in enumerate(sorted_individuals)
            ]
            if not top_user and individual_ranking:
                top_user = individual_ranking[0].get("user_id") or individual_ranking[0].get("username")

        return {
            "top_team": top_team,
            "top_user": top_user,
            "team_ranking": team_ranking,
            "individual_ranking": individual_ranking,
            "total_submissions": len(submissions_payload),
            "total_solves": len(solves_payload),
        }

    @staticmethod
    def _build_challenge_stats(challenges_payload, submissions_payload, solves_payload):
        """按题目维度统计提交/解题数量，附带题目元信息"""
        sub_count: dict[str, int] = {}
        for sub in submissions_payload:
            slug = sub.get("challenge")
            if slug:
                sub_count[slug] = sub_count.get(slug, 0) + 1
        solve_count: dict[str, int] = {}
        for solve in solves_payload:
            slug = solve.get("challenge")
            if slug:
                solve_count[slug] = solve_count.get(slug, 0) + 1
        stats = []
        for ch in challenges_payload:
            stats.append(
                {
                    "challenge": ch,
                    "submissions": sub_count.get(ch.get("slug"), 0),
                    "solves": solve_count.get(ch.get("slug"), 0),
                }
            )
        return stats
