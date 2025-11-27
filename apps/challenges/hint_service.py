# apps/challenges/hint_service.py

from __future__ import annotations

from django.db import transaction

from apps.common.base.base_service import BaseService
from apps.common.exceptions import ValidationError
from apps.accounts.models import User
from apps.contests.services import ContestContextService
from apps.contests.repo import TeamMemberRepo

from .models import Challenge
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
        self.contest_service.ensure_contest_started(contest)
        challenge = self.challenge_repo.get_by_slug(contest=contest, slug=challenge_slug)
        membership = self.member_repo.get_membership(contest=contest, user=user)
        hints = self.hint_repo.list_for_challenge(challenge)
        payload = []
        for hint in hints:
            unlocked = hint.is_free or self.unlock_repo.has_unlocked(hint=hint, user=user)
            payload.append(serialize_hint(hint, unlocked=unlocked))
        return payload

    @transaction.atomic
    def _unlock(self, user: User, *, contest_slug: str, challenge_slug: str, hint_id: int, schema: HintUnlockSchema):
        """解锁提示：记录解锁信息，暂不扣分（预留计分调整 TODO）"""
        _ = schema  # 预留扩展字段
        contest = self.contest_service.get_contest(contest_slug)
        self.contest_service.ensure_contest_started(contest)
        challenge = self.challenge_repo.get_by_slug(contest=contest, slug=challenge_slug)
        hint = self.hint_repo.get_by_id(hint_id)
        if hint.challenge_id != challenge.id:
            raise ValidationError(message="提示不属于当前题目")

        membership = self.member_repo.get_membership(contest=contest, user=user)
        if hint.is_free or self.unlock_repo.has_unlocked(hint=hint, user=user):
            return serialize_hint(hint, unlocked=True)

        # TODO: 若需扣减得分/积分，在此处接入计分逻辑
        self.unlock_repo.create_unlock(
            hint=hint,
            challenge=challenge,
            user=user,
            team=membership.team if membership else None,
            cost=hint.cost,
        )
        return serialize_hint(hint, unlocked=True)
