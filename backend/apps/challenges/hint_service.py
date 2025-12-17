# apps/challenges/hint_service.py

from __future__ import annotations

from django.db import transaction

from apps.common.base.base_service import BaseService
from apps.common.exceptions import ValidationError
from apps.accounts.models import User
from apps.contests.services import ContestContextService
from apps.contests.repo import TeamMemberRepo
from apps.common.ws_utils import broadcast_notify, broadcast_contest
from apps.notifications.services import create_and_push_notification, build_dedup_key
from apps.notifications.models import Notification
from apps.submissions.services import SubmissionService

from .repo import ChallengeRepo, ChallengeHintRepo, ChallengeHintUnlockRepo
from .schemas import HintUnlockSchema
from .serializers import serialize_hint


class ChallengeHintService(BaseService[dict]):
    """
    提示服务：
    - 列出提示并标记是否解锁
    - 扣分提示需先解锁后返回内容
    - 业务场景：比赛中选手查看/解锁题目提示，计入扣分
    """

    atomic_enabled = False

    def __init__(
            self,
            contest_service: ContestContextService | None = None,
            challenge_repo: ChallengeRepo | None = None,
            hint_repo: ChallengeHintRepo | None = None,
            unlock_repo: ChallengeHintUnlockRepo | None = None,
            member_repo: TeamMemberRepo | None = None,
    ):
        self.contest_service = contest_service or ContestContextService()
        self.challenge_repo = challenge_repo or ChallengeRepo()
        self.hint_repo = hint_repo or ChallengeHintRepo()
        self.unlock_repo = unlock_repo or ChallengeHintUnlockRepo()
        self.member_repo = member_repo or TeamMemberRepo()
        # 使用解锁仓储，确保提示扣分在可见分值计算时生效
        self.submission_service = SubmissionService(hint_repo=self.unlock_repo)

    def perform(
            self,
            user: User,
            *,
            action: str,
            contest_slug: str,
            challenge_slug: str,
            hint_id: int | None = None,
            schema: HintUnlockSchema | None = None,
    ) -> dict | list[dict]:
        """
        统一入口：
        - action=list：返回提示列表（未解锁内容为空）
        - action=unlock：解锁指定提示并返回内容
        """
        if action == "list":
            return self._list_hints(user, contest_slug=contest_slug, challenge_slug=challenge_slug)
        if action == "unlock":
            if hint_id is None:
                raise ValidationError(message="缺少提示 ID")
            schema = schema or HintUnlockSchema()
            return self._unlock(
                user,
                contest_slug=contest_slug,
                challenge_slug=challenge_slug,
                hint_id=hint_id,
                schema=schema,
            )
        raise ValidationError(message="不支持的提示操作")

    def _list_hints(self, user: User, *, contest_slug: str, challenge_slug: str) -> list[dict]:
        """返回提示列表，未解锁的提示不返回内容"""
        contest = self.contest_service.get_contest(contest_slug)
        self.contest_service.ensure_contest_visible(contest, user)
        self.contest_service.ensure_contest_started(contest)
        challenge = self.challenge_repo.get_by_slug(contest=contest, slug=challenge_slug)
        membership = self.member_repo.get_membership(contest=contest, user=user)
        hints = self.hint_repo.list_for_challenge(challenge)
        payload = []
        for hint in hints:
            unlocked = self.unlock_repo.has_unlocked(
                hint=hint,
                user=user,
                team=getattr(membership, "team", None),
            )
            payload.append(serialize_hint(hint, unlocked=unlocked))
        return payload

    @transaction.atomic
    def _unlock(self, user: User, *, contest_slug: str, challenge_slug: str, hint_id: int, schema: HintUnlockSchema):
        """解锁提示：记录解锁信息并计入扣分成本"""
        _ = schema  # 预留扩展字段
        contest = self.contest_service.get_contest(contest_slug)
        self.contest_service.ensure_contest_visible(contest, user)
        self.contest_service.ensure_contest_running(contest)
        challenge = self.challenge_repo.get_by_slug(contest=contest, slug=challenge_slug)
        hint = self.hint_repo.get_by_id(hint_id)
        if getattr(hint, "challenge_id", None) != getattr(challenge, "id", None):
            raise ValidationError(message="提示不属于当前题目")

        membership = self.member_repo.get_membership(contest=contest, user=user)
        if self.unlock_repo.has_unlocked(
                hint=hint,
                user=user,
                team=getattr(membership, "team", None),
        ):
            return serialize_hint(hint, unlocked=True)

        self.unlock_repo.create_unlock(
            hint=hint,
            challenge=challenge,
            user=user,
            team=membership.team if membership else None,
            cost=hint.cost if not hint.is_free else 0,
        )
        payload = serialize_hint(hint, unlocked=True)
        total_cost = self.unlock_repo.cost_for_solver(
            challenge=challenge,
            user=user,
            team=getattr(membership, "team", None),
        )
        payload["total_cost"] = total_cost
        try:
            # 计算解锁后当前可得分（含提示扣分/动态衰减），便于前端刷新显示
            current_points = self.submission_service.visible_points_for_user(
                user,
                contest,
                challenge,
                membership=membership,
            )
            payload["current_points"] = current_points
        except Exception:
            pass
        hint_brief = {
            "id": getattr(hint, "id", None),
            "title": hint.title,
            "is_free": hint.is_free,
            "cost": hint.cost,
            "order": hint.order,
        }
        # WebSocket 通知：个人与比赛组推送提示解锁事件
        broadcast_notify(
            getattr(user, "id", None),
            {
                "event": "hint_unlocked",
                "contest": contest.slug,
                "challenge": challenge.slug,
                "hint_id": getattr(hint, "id", None),
                "cost": hint.cost,
                "hint": payload,
            },
        )
        broadcast_contest(
            contest.slug,
            {
                "event": "hint_unlocked",
                "contest": contest.slug,
                "challenge": challenge.slug,
                "hint_id": getattr(hint, "id", None),
                "user_id": getattr(user, "id", None),
                "team_id": getattr(membership, "team_id", None),
                "hint": hint_brief,
            },
        )
        # 队伍内广播通知（仅团队赛），避免全场知晓详情
        if contest.is_team_based and membership and getattr(membership, "team", None):
            team = membership.team
            members = list(self.member_repo.active_members(team))
            dedup = build_dedup_key(
                type="hint_unlocked",
                contest=contest,
                team=team,
                challenge=challenge,
                extra=str(getattr(hint, "id", None)),
            )
            for m in members:
                create_and_push_notification(
                    getattr(m, "user", None),
                    type=Notification.Type.HINT_UNLOCKED,
                    title=f"队伍提示解锁：{challenge.title}",
                    body=hint.title,
                    payload={
                        "contest": contest.slug,
                        "challenge": challenge.slug,
                        "hint_id": getattr(hint, "id", None),
                        "team_id": getattr(team, "id", None),
                        "by_user_id": getattr(user, "id", None),
                    },
                    contest=contest,
                    team=team,
                    challenge=challenge,
                    dedup_key=dedup,
                )
        return payload
