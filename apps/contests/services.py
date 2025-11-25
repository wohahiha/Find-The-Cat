from __future__ import annotations

import secrets
from typing import Optional

from django.utils import timezone

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
from apps.challenges.repo import ChallengeRepo, ChallengeSolveRepo, ChallengeHintUnlockRepo
from apps.challenges.serializers import serialize_challenge
from apps.submissions.repo import SubmissionRepo
from apps.common.infra import redis_client
from apps.common.utils.redis_keys import scoreboard_key

from .models import Contest, Team, TeamMember, ContestAnnouncement
from .repo import ContestRepo, TeamRepo, TeamMemberRepo, ContestAnnouncementRepo
from .schemas import (
    ContestCreateSchema,
    TeamCreateSchema,
    TeamJoinSchema,
    TeamLeaveSchema,
    TeamDisbandSchema,
    AnnouncementCreateSchema,
    TeamInviteResetSchema,
    TeamTransferSchema,
)

# 服务层：实现比赛、公告、队伍的业务流程，依赖仓储与 Schema 校验。


def serialize_contest(contest: Contest) -> dict:
    """比赛序列化：提供比赛基础信息与状态，用于 API 返回。"""
    return {
        "id": contest.id,
        "name": contest.name,
        "slug": contest.slug,
        "description": contest.description,
        "visibility": contest.visibility,
        "start_time": contest.start_time,
        "end_time": contest.end_time,
        "freeze_time": contest.freeze_time,
        "is_team_based": contest.is_team_based,
        "max_team_members": contest.max_team_members,
        "is_active": contest.is_active,
    }


def serialize_announcement(announcement: ContestAnnouncement) -> dict:
    """公告序列化：返回基础信息与时间戳。"""
    return {
        "id": announcement.id,
        "contest": announcement.contest.slug,
        "title": announcement.title,
        "content": announcement.content,
        "is_active": announcement.is_active,
        "created_at": announcement.created_at,
        "updated_at": announcement.updated_at,
    }


def serialize_team(team: Team) -> dict:
    """队伍序列化：包含队长、邀请码、成员数量等。"""
    return {
        "id": team.id,
        "contest": team.contest.slug,
        "name": team.name,
        "slug": team.slug,
        "description": team.description,
        "captain_id": team.captain_id,
        "invite_token": team.invite_token,
        "member_count": team.member_count,
        "is_active": team.is_active,
    }


class ContestContextService(BaseService[Contest]):
    """
    提供统一的比赛上下文（状态校验、成员关系等）。
    """

    def __init__(
        self,
        contest_repo: ContestRepo | None = None,
        member_repo: TeamMemberRepo | None = None,
        team_repo: TeamRepo | None = None,
    ):
        """注入比赛、成员、队伍仓储，方便在上下文校验中复用。"""
        # 仓储依赖注入：默认使用实际仓储，便于测试时替换
        self.contest_repo = contest_repo or ContestRepo()
        self.member_repo = member_repo or TeamMemberRepo()
        self.team_repo = team_repo or TeamRepo()
        # 公告仓储：用于列表查询
        self.announcement_repo = ContestAnnouncementRepo()

    def get_contest(self, slug: str) -> Contest:
        """根据 slug 获取比赛对象。"""
        return self.contest_repo.get_by_slug(slug)

    def ensure_contest_started(self, contest: Contest) -> None:
        """校验比赛已开赛，否则抛业务校验错误。"""
        if not contest.has_started:
            raise ValidationError(message="比赛尚未开始")

    def ensure_contest_not_ended(self, contest: Contest) -> None:
        """校验比赛未结束。"""
        if contest.has_ended:
            raise ValidationError(message="比赛已结束")

    def ensure_contest_running(self, contest: Contest) -> None:
        """组合校验：比赛已开始且未结束。"""
        self.ensure_contest_started(contest)
        self.ensure_contest_not_ended(contest)

    def get_user_membership(self, contest: Contest, user: User):
        """查询用户在比赛中的队伍关系。"""
        return self.member_repo.get_membership(contest=contest, user=user)

    def get_user_team(self, contest: Contest, user: User) -> Optional[Team]:
        """获取用户所在队伍，若无则返回 None。"""
        membership = self.get_user_membership(contest=contest, user=user)
        return membership.team if membership else None

    def perform(self, *args, **kwargs) -> Contest:
        """ContextService 不提供通用执行入口，防止误用 execute。"""
        raise NotImplementedError("ContestContextService does not support execute()")

    def list_announcements(self, contest: Contest):
        """获取比赛公告列表（仅返回有效公告）。"""
        return self.announcement_repo.list_active(contest)


def serialize_team_member(member: TeamMember) -> dict:
    """队伍成员序列化：导出场景下附带用户基础标识。"""
    return {
        "user_id": member.user_id,
        "username": member.user.username if member.user_id else None,
        "role": member.role,
        "is_active": member.is_active,
        "joined_at": member.joined_at,
    }


class CreateContestService(BaseService[Contest]):
    """创建比赛：封装仓储写入与 Schema 转换。"""
    def __init__(self, repo: ContestRepo | None = None):
        """允许外部传入自定义仓储，默认使用实际仓储。"""
        self.repo = repo or ContestRepo()

    def perform(self, schema: ContestCreateSchema) -> Contest:
        """将校验后的比赛入参写入数据库，生成新的比赛记录。"""
        # 将 Schema 转为字典，去除无关字段后落库
        data = schema.to_dict(exclude_none=True)
        data.pop("contest_slug", None)
        return self.repo.create(data)


class ContestAnnouncementService(BaseService[ContestAnnouncement]):
    """
    管理比赛公告的服务：创建公告并返回记录。
    """

    def __init__(
        self,
        contest_repo: ContestRepo | None = None,
        announcement_repo: ContestAnnouncementRepo | None = None,
    ):
        """注入比赛与公告仓储，便于单元测试替换。"""
        # 比赛仓储：根据 slug 拉取比赛
        self.contest_repo = contest_repo or ContestRepo()
        # 公告仓储：持久化公告内容
        self.announcement_repo = announcement_repo or ContestAnnouncementRepo()

    def perform(self, schema: AnnouncementCreateSchema) -> ContestAnnouncement:
        """根据比赛标识创建公告，保持公告与比赛的关联关系。"""
        contest = self.contest_repo.get_by_slug(schema.contest_slug)
        payload = schema.to_dict(exclude_none=True)
        payload.pop("contest_slug", None)
        payload["contest"] = contest
        return self.announcement_repo.create(payload)


class TeamCreateService(BaseService[Team]):
    """
    创建队伍服务：
    - 校验用户角色与比赛状态。
    - 自动创建队伍并将创建者设为队长成员。
    """

    def __init__(
        self,
        contest_repo: ContestRepo | None = None,
        team_repo: TeamRepo | None = None,
        member_repo: TeamMemberRepo | None = None,
    ):
        """注入比赛、队伍、成员仓储，便于不同环境下替换实现。"""
        # 注入比赛、队伍、成员仓储，便于服务层统一调用
        self.contest_repo = contest_repo or ContestRepo()
        self.team_repo = team_repo or TeamRepo()
        self.member_repo = member_repo or TeamMemberRepo()

    def perform(self, user: User, schema: TeamCreateSchema) -> Team:
        """以当前用户为队长创建队伍，完成唯一 slug 与成员记录写入。"""
        # 1) 获取比赛并校验管理员不可参赛、比赛允许组队、未结束
        contest = self.contest_repo.get_by_slug(schema.contest_slug)
        if user.is_staff:
            raise ValidationError(message="管理员账号无法参与比赛")
        if not contest.is_team_based:
            raise ValidationError(message="该比赛不支持组队")
        if contest.has_ended:
            raise ConflictError(message="比赛已结束，无法创建队伍")
        # 2) 校验用户尚未加入该比赛的任何队伍
        existing = self.member_repo.get_membership(contest=contest, user=user)
        if existing:
            raise ConflictError(message="您已加入该比赛的队伍")
        # 3) 创建队伍并写入队长成员记录
        team = self.team_repo.create_team(
            contest=contest,
            captain=user,
            name=schema.name,
            description=schema.description,
        )
        self.member_repo.create_member(team=team, user=user, role=TeamMember.Role.CAPTAIN)
        return team


class TeamJoinService(BaseService[TeamMember]):
    """
    加入队伍服务：
    - 校验邀请码有效、人数未满、用户未加入其他队伍、比赛未结束。
    """

    def __init__(
        self,
        contest_repo: ContestRepo | None = None,
        team_repo: TeamRepo | None = None,
        member_repo: TeamMemberRepo | None = None,
    ):
        """注入比赛、队伍、成员仓储，供加入校验与写入使用。"""
        # 仓储依赖：用于查询比赛、队伍与成员关系
        self.contest_repo = contest_repo or ContestRepo()
        self.team_repo = team_repo or TeamRepo()
        self.member_repo = member_repo or TeamMemberRepo()

    def perform(self, user: User, schema: TeamJoinSchema) -> TeamMember:
        """校验并将用户加入目标队伍，返回成员关系记录。"""
        # 1) 获取比赛并禁止管理员加入
        contest = self.contest_repo.get_by_slug(schema.contest_slug)
        if user.is_staff:
            raise ValidationError(message="管理员账号无法加入队伍")
        # 2) 根据邀请码查找队伍
        team = (
            self.team_repo.filter(contest=contest, invite_token=schema.invite_token, is_active=True)
            .select_related("contest")
            .first()
        )
        if team is None:
            raise NotFoundError(message="邀请码无效")
        # 3) 校验人数上限、用户未在其他队伍、比赛未结束
        if team.member_count >= contest.max_team_members:
            raise ConflictError(message="队伍人数已满")
        if self.member_repo.get_membership(contest=contest, user=user):
            raise ConflictError(message="您已经加入了一支队伍")
        if contest.has_ended:
            raise ConflictError(message="比赛已结束，无法加入队伍")
        return self.member_repo.create_member(team=team, user=user, role=TeamMember.Role.MEMBER)


class TeamLeaveService(BaseService[None]):
    """
    退出队伍服务：
    - 校验用户是否在队伍中。
    - 队长需先解散或移交后才能退出。
    """

    def __init__(
        self,
        contest_repo: ContestRepo | None = None,
        member_repo: TeamMemberRepo | None = None,
    ):
        """注入比赛与成员仓储，便于读取当前成员关系。"""
        # 仓储依赖：用于校验比赛与当前成员关系
        self.contest_repo = contest_repo or ContestRepo()
        self.member_repo = member_repo or TeamMemberRepo()

    def perform(self, user: User, schema: TeamLeaveSchema) -> None:
        """处理成员退出队伍，队长且多人时阻止直接退出。"""
        # 1) 获取比赛与当前成员关系
        contest = self.contest_repo.get_by_slug(schema.contest_slug)
        membership = self.member_repo.get_membership(contest=contest, user=user)
        if not membership:
            raise NotFoundError(message="你尚未加入任何队伍")
        # 2) 队长且队伍多人时禁止直接退出
        if membership.role == TeamMember.Role.CAPTAIN:
            team = membership.team
            if team.member_count > 1:
                raise ConflictError(message="队长请先将队伍解散或移交队长后再退出")
        # 3) 标记成员无效
        self.member_repo.remove_member(membership)


class TeamDisbandService(BaseService[Team]):
    """
    解散队伍服务：
    - 队长或管理员可操作。
    - 逐个成员失效并关闭队伍。
    """

    def __init__(
        self,
        team_repo: TeamRepo | None = None,
        member_repo: TeamMemberRepo | None = None,
    ):
        """注入队伍与成员仓储，便于批量标记成员失效。"""
        # 仓储依赖：队伍与成员查询/更新
        self.team_repo = team_repo or TeamRepo()
        self.member_repo = member_repo or TeamMemberRepo()

    def perform(self, user: User, schema: TeamDisbandSchema) -> Team:
        """解散目标队伍，逐个成员失效并关闭队伍记录。"""
        # 1) 校验权限：仅队长或管理员
        team = self.team_repo.get_by_id(schema.team_id)
        if not (user.is_staff or team.captain_id == user.id):
            raise PermissionDeniedError(message="只有队长或管理员可以解散队伍")
        # 2) 标记所有成员失效
        for member in self.member_repo.active_members(team):
            member.is_active = False
            member.save(update_fields=["is_active"])
        # 3) 关闭队伍并重置邀请码，避免复用
        team.is_active = False
        team.invite_token = secrets.token_hex(4)
        team.save(update_fields=["is_active", "invite_token", "updated_at"])
        return team


class TeamInviteResetService(BaseService[Team]):
    """重置队伍邀请码：仅队长或管理员可操作。"""

    def __init__(self, team_repo: TeamRepo | None = None):
        """允许注入自定义队伍仓储以便测试或替换实现。"""
        # 队伍仓储：用于重置邀请码时读取与更新队伍
        self.team_repo = team_repo or TeamRepo()

    def perform(self, user: User, schema: TeamInviteResetSchema) -> Team:
        """校验队伍有效性与操作者权限后重置邀请码。"""
        team = self.team_repo.get_by_id(schema.team_id)
        if not team.is_active:
            raise ConflictError(message="队伍已失效，无法重置邀请码")
        if not (user.is_staff or team.captain_id == user.id):
            raise PermissionDeniedError(message="仅队长或管理员可重置邀请码")
        # 使用随机 token 生成新邀请码
        token = secrets.token_hex(4)
        return self.team_repo.reset_invite_token(team, token=token)


class TeamTransferService(BaseService[Team]):
    """队长移交：将队长角色转给指定队员。"""

    def __init__(
        self,
        team_repo: TeamRepo | None = None,
        member_repo: TeamMemberRepo | None = None,
    ):
        """注入队伍与成员仓储，支持扩展或测试替换。"""
        # 仓储依赖：负责读取队伍状态与成员关系
        self.team_repo = team_repo or TeamRepo()
        self.member_repo = member_repo or TeamMemberRepo()

    @transaction.atomic
    def perform(self, user: User, schema: TeamTransferSchema) -> Team:
        """在事务内完成队长权限转移，确保成员关系与队长字段一致。"""
        # 1) 校验队伍有效与操作者权限
        team = self.team_repo.get_by_id(schema.team_id)
        if not team.is_active:
            raise ConflictError(message="队伍已失效，无法移交队长")
        if not (user.is_staff or team.captain_id == user.id):
            raise PermissionDeniedError(message="仅队长或管理员可移交队长")
        # 2) 查找或创建目标成员记录
        target_user = User.objects.filter(pk=schema.new_captain_id).first()
        if not target_user:
            raise NotFoundError(message="目标用户不存在")
        membership = self.member_repo.filter(team=team, user_id=target_user.id).first()
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
        old_captain_id = team.captain_id
        team.captain_id = target_user.id
        team.save(update_fields=["captain_id", "updated_at"])
        membership.role = TeamMember.Role.CAPTAIN
        membership.save(update_fields=["role"])
        self.member_repo.filter(team=team, user_id=old_captain_id).update(role=TeamMember.Role.MEMBER, is_active=True)
        return team


class ScoreboardService(BaseService[list[dict]]):
    """
    记分板服务：
    - 汇总比赛内的解题记录，按分数与时间排序生成排名。
    - 支持 Redis 缓存以减轻重复计算开销。
    """
    atomic_enabled = False
    cache_ttl_seconds: int = 30

    def perform(self, contest: Contest) -> list[dict]:
        """计算记分板：汇总解题记录并排序。"""
        cache_key = self.cache_key(contest.id)
        cached = redis_client.get_json(cache_key)
        if isinstance(cached, list):
            return cached

        # 1) 计算封榜/截止时间，封榜后只统计封榜前的解题；否则以比赛结束时间为上限
        now = timezone.now()
        cutoff = contest.end_time
        if contest.freeze_time and now >= contest.freeze_time:
            cutoff = min(contest.freeze_time, contest.end_time)

        # 2) 查询满足时间窗口的解题，按时间排序
        solves = (
            ChallengeSolve.objects.filter(challenge__contest=contest, solved_at__lte=cutoff)
            .select_related("challenge", "team", "user")
            .order_by("solved_at")
        )
        board: dict[str, dict] = {}
        for solve in solves:
            key: str
            entry: dict
            if contest.is_team_based and solve.team:
                # 组队赛：按队伍汇总
                key = f"team-{solve.team_id}"
                entry = board.setdefault(
                    key,
                    {
                        "type": "team",
                        "team": serialize_team(solve.team),
                        "score": 0,
                        "last_solve": solve.solved_at,
                        "solves": [],
                    },
                )
            else:
                # 个人赛：按用户汇总
                key = f"user-{solve.user_id}"
                entry = board.setdefault(
                    key,
                    {
                        "type": "user",
                        "user": {
                            "id": solve.user_id,
                            "username": solve.user.username,
                        },
                        "score": 0,
                        "last_solve": solve.solved_at,
                        "solves": [],
                    },
                )
            entry["score"] += solve.awarded_points
            entry["last_solve"] = solve.solved_at
            entry["solves"].append(
                {
                    "challenge": solve.challenge.slug,
                    "points": solve.awarded_points,
                    "solved_at": solve.solved_at,
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
    def cache_key(contest_id: int) -> str:
        # 生成记分板缓存键，便于缓存读写
        return scoreboard_key(contest_id)

    @classmethod
    def invalidate_cache(cls, contest_id: int) -> None:
        # 主动失效记分板缓存，供提交/判题后调用
        redis_client.delete(cls.cache_key(contest_id))


class ContestExportService(BaseService[dict]):
    """
    比赛数据导出服务：
    - 提供比赛基础信息、队伍成员、题目、解题记录与提交记录。
    - 管理端使用，用于备份或运营分析。
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
    ):
        """集中注入比赛、队伍、成员、题目、解题、提交与榜单依赖。"""
        # 仓储与服务依赖：集中注入，方便测试替换
        self.contest_repo = contest_repo or ContestRepo()
        self.team_repo = team_repo or TeamRepo()
        self.member_repo = member_repo or TeamMemberRepo()
        self.challenge_repo = challenge_repo or ChallengeRepo()
        self.solve_repo = solve_repo or ChallengeSolveRepo()
        self.submission_repo = submission_repo or SubmissionRepo()
        self.scoreboard_service = scoreboard_service or ScoreboardService()
        self.hint_unlock_repo = hint_unlock_repo or ChallengeHintUnlockRepo()

    def perform(self, contest_slug: str) -> dict:
        """导出指定比赛的数据快照。"""
        contest = self.contest_repo.get_by_slug(contest_slug)

        # 队伍与成员
        teams_payload = []
        teams = self.team_repo.filter(contest=contest).select_related("captain")
        members_qs = self.member_repo.filter(team__contest=contest).select_related("user", "team")
        members_by_team: dict[int, list[TeamMember]] = {}
        for member in members_qs:
            members_by_team.setdefault(member.team_id, []).append(member)

        for team in teams:
            payload = serialize_team(team)
            payload["members"] = [serialize_team_member(m) for m in members_by_team.get(team.id, [])]
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
                "challenge": solve.challenge.slug,
                "user": solve.user_id,
                "username": solve.user.username if solve.user_id else None,
                "team": solve.team_id,
                "awarded_points": solve.awarded_points,
                "solved_at": solve.solved_at,
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
                "id": sub.id,
                "contest": sub.contest.slug,
                "challenge": sub.challenge.slug,
                "user": sub.user_id,
                "team": sub.team_id,
                "status": sub.status,
                "is_correct": sub.is_correct,
                "awarded_points": sub.awarded_points,
                "blood_rank": sub.blood_rank,
                "message": sub.message,
                "solve_id": sub.solve_id,
                "created_at": sub.created_at,
                "judged_at": sub.judged_at,
            }
            for sub in submissions
        ]

        # 记分板快照（与详情页相同计算逻辑）
        scoreboard_payload = self.scoreboard_service.execute(contest)

        return {
            "contest": serialize_contest(contest),
            "teams": teams_payload,
            "challenges": challenges_payload,
            "solves": solves_payload,
            "submissions": submissions_payload,
            "scoreboard": scoreboard_payload,
        }
