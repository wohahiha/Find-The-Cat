# apps/challenges/challenge_crud_service.py

from __future__ import annotations

from django.utils import timezone

from apps.common.base.base_service import BaseService
from apps.common.exceptions import ValidationError
from apps.accounts.models import User
from apps.contests.repo import ContestRepo
from apps.notifications.services import fanout_notifications, build_dedup_key
from apps.notifications.models import Notification
from apps.contests.repo import ContestParticipantRepo

from .models import Challenge
from .repo import (
    ChallengeRepo,
    ChallengeCategoryRepo,
    ChallengeTaskRepo,
    ChallengeAttachmentRepo,
    ChallengeHintRepo,
)
from .schemas import ChallengeCreateSchema, ChallengeUpdateSchema
from apps.common.infra.logger import get_logger, logger_extra
from apps.common.ws_utils import broadcast_contest

logger = get_logger(__name__)


def serialize_challenge_brief(challenge: Challenge) -> dict:
    """题目简要信息：用于 WebSocket 推送，避免前端二次拉取"""
    hints_qs = getattr(challenge, "hints", None)
    tasks_qs = getattr(challenge, "tasks", None)
    attachments_qs = getattr(challenge, "attachments", None)
    hints_count = hints_qs.count() if hints_qs is not None else 0
    free_hint_count = hints_qs.filter(is_free=True).count() if hints_qs is not None else 0
    updated_at = getattr(challenge, "updated_at", None)
    updated_at_str = updated_at.isoformat() if hasattr(updated_at, "isoformat") else updated_at
    has_machine = bool(getattr(challenge, "has_machine", False))
    return {
        "id": getattr(challenge, "id", None),
        "contest": getattr(challenge.contest, "slug", None),
        "slug": challenge.slug,
        "title": challenge.title,
        "category": getattr(challenge.category, "name", None),
        "difficulty": challenge.difficulty,
        "base_points": challenge.base_points,
        "min_score": challenge.min_score,
        "scoring_mode": challenge.scoring_mode,
        "decay_type": challenge.decay_type,
        "decay_factor": challenge.decay_factor,
        "blood_reward_type": challenge.blood_reward_type,
        "is_active": challenge.is_active,
        "has_machine": has_machine,
        "tasks_count": tasks_qs.count() if tasks_qs is not None else 0,
        "attachments_count": attachments_qs.count() if attachments_qs is not None else 0,
        "hints_count": hints_count,
        "free_hint_count": free_hint_count,
        "updated_at": updated_at_str,
    }


class ChallengeCreateService(BaseService[Challenge]):
    """
    创建题目服务：
    - 校验并创建题目，同时写入子任务、附件与提示
    - 自动处理分类与作者关联
    - 适用于管理员在比赛中新增题目
    """

    def __init__(
            self,
            contest_repo: ContestRepo | None = None,
            challenge_repo: ChallengeRepo | None = None,
            category_repo: ChallengeCategoryRepo | None = None,
            task_repo: ChallengeTaskRepo | None = None,
            attachment_repo: ChallengeAttachmentRepo | None = None,
            hint_repo: ChallengeHintRepo | None = None,
            participant_repo: ContestParticipantRepo | None = None,
    ):
        self.contest_repo = contest_repo or ContestRepo()
        self.challenge_repo = challenge_repo or ChallengeRepo()
        self.category_repo = category_repo or ChallengeCategoryRepo()
        self.task_repo = task_repo or ChallengeTaskRepo()
        self.attachment_repo = attachment_repo or ChallengeAttachmentRepo()
        self.hint_repo = hint_repo or ChallengeHintRepo()
        self.participant_repo = participant_repo or ContestParticipantRepo()

    def perform(self, user: User, schema: ChallengeCreateSchema) -> Challenge:
        # 1) 获取比赛与分类（可选创建）
        contest = self.contest_repo.get_by_slug(schema.contest_slug)
        category = None
        if schema.category:
            category = self.category_repo.resolve_for_contest(contest, schema.category)
            if category is None:
                raise ValidationError(message="该题目分类未在当前比赛中配置")
        # 2) 准备 payload 并剥离子任务/附件
        payload = schema.to_dict(exclude_none=True)
        payload.pop("contest_slug", None)
        payload.update({"contest": contest, "category": category, "author": user})
        # 动态计分默认最低分为基础分一半
        if payload.get("min_score") is None:
            payload["min_score"] = max(1, int(payload.get("base_points", 100)) // 2)
        # 规范 n 血奖励配置
        reward_type = payload.get("blood_reward_type")
        reward_count = int(payload.get("blood_reward_count") or 0)
        bonus_list = list(payload.get("blood_bonus_points") or [])
        if reward_type != Challenge.BloodRewardType.BONUS:
            payload["blood_bonus_points"] = []
        else:
            payload["blood_bonus_points"] = bonus_list[:reward_count]
        if reward_type == Challenge.BloodRewardType.NONE:
            payload["blood_reward_count"] = 0
        tasks = payload.pop("tasks", [])
        attachments = payload.pop("attachments", [])
        hints = payload.pop("hints", [])
        # 3) 创建题目并同步子任务/附件/提示
        challenge = self.challenge_repo.create(payload)
        self._sync_tasks(challenge, tasks)  # type: ignore[attr-defined]
        self._sync_attachments(challenge, attachments)  # type: ignore[attr-defined]
        self._sync_hints(challenge, hints)  # type: ignore[attr-defined]
        logger.info(
            "创建题目",
            extra=logger_extra(
                {"challenge": challenge.slug, "contest": contest.slug, "user_id": getattr(user, "id", None)}
            ),
        )
        # WebSocket：创建后推送题目摘要，便于前端刷新列表
        broadcast_contest(
            contest.slug,
            {
                "event": "challenge_created",
                "contest": contest.slug,
                "challenge": challenge.slug,
                "data": serialize_challenge_brief(challenge),
            },
        )
        # 系统通知：比赛内新题
        participants = list(self.participant_repo.filter(contest=contest, is_valid=True).select_related("user"))
        if participants:
            dedup = build_dedup_key(
                type=Notification.Type.CHALLENGE_NEW,
                contest=contest,
                challenge=challenge,
            )
            fanout_notifications(
                [p.user for p in participants if getattr(p, "user", None)],
                type=Notification.Type.CHALLENGE_NEW,
                title=f"新题上线：{challenge.title}",
                body=contest.name,
                payload={
                    "contest": contest.slug,
                    "challenge": challenge.slug,
                },
                contest=contest,
                challenge=challenge,
                dedup_key=dedup,
            )
        return challenge

    def _sync_tasks(self, challenge: Challenge, tasks_data: list) -> None:
        """创建子任务列表：支持多阶段得分"""
        for idx, task in enumerate(tasks_data, start=1):
            self.task_repo.create(
                {
                    "challenge": challenge,
                    "title": task.get("title", ""),
                    "description": task.get("description", ""),
                    "points": int(task.get("points", 0)),
                    "order": int(task.get("order", idx)),
                }
            )

    def _sync_attachments(self, challenge: Challenge, attachments_data: list) -> None:
        """创建附件列表：记录附件名称与下载链接"""
        for idx, att in enumerate(attachments_data, start=1):
            self.attachment_repo.create(
                {
                    "challenge": challenge,
                    "name": att.get("name", f"附件{idx}"),
                    "url": att.get("url", ""),
                    "order": int(att.get("order", idx)),
                }
            )

    def _sync_hints(self, challenge: Challenge, hints_data: list) -> None:
        """创建提示列表：支持免费/扣分提示"""
        for idx, hint in enumerate(hints_data, start=1):
            self.hint_repo.create(
                {
                    "challenge": challenge,
                    "title": hint.get("title", f"提示{idx}"),
                    "content": hint.get("content", ""),
                    "is_free": bool(hint.get("is_free", True)),
                    "cost": int(hint.get("cost", 0)),
                    "order": int(hint.get("order", idx)),
                }
            )


class ChallengeUpdateService(BaseService[Challenge]):
    """更新题目服务：支持分类替换、子任务/附件/提示全量替换"""

    def __init__(
            self,
            contest_repo: ContestRepo | None = None,
            challenge_repo: ChallengeRepo | None = None,
            category_repo: ChallengeCategoryRepo | None = None,
            task_repo: ChallengeTaskRepo | None = None,
            attachment_repo: ChallengeAttachmentRepo | None = None,
            hint_repo: ChallengeHintRepo | None = None,
            participant_repo: ContestParticipantRepo | None = None,
    ):
        self.contest_repo = contest_repo or ContestRepo()
        self.challenge_repo = challenge_repo or ChallengeRepo()
        self.category_repo = category_repo or ChallengeCategoryRepo()
        self.task_repo = task_repo or ChallengeTaskRepo()
        self.attachment_repo = attachment_repo or ChallengeAttachmentRepo()
        self.hint_repo = hint_repo or ChallengeHintRepo()
        self.participant_repo = participant_repo or ContestParticipantRepo()

    def perform(self, schema: ChallengeUpdateSchema) -> Challenge:
        # 1) 获取比赛与题目
        contest = self.contest_repo.get_by_slug(schema.contest_slug)
        challenge = self.challenge_repo.get_by_slug(contest=contest, slug=schema.slug)
        # 2) 处理分类
        category = challenge.category
        if schema.category:
            category = self.category_repo.resolve_for_contest(contest, schema.category)
            if category is None:
                raise ValidationError(message="该题目分类未在当前比赛中配置")
        # 3) 更新字段并保存
        payload = schema.to_dict(exclude_none=True)
        payload.pop("contest_slug", None)
        if payload.get("min_score") is None and "base_points" in payload:
            payload["min_score"] = max(1, int(payload.get("base_points", 100)) // 2)
        reward_type = payload.get("blood_reward_type", challenge.blood_reward_type)
        reward_count = int(payload.get("blood_reward_count", challenge.blood_reward_count) or 0)
        bonus_list = payload.get("blood_bonus_points", list(challenge.blood_bonus_points))
        if reward_type != Challenge.BloodRewardType.BONUS:
            payload["blood_bonus_points"] = []
        else:
            payload["blood_bonus_points"] = list(bonus_list)[:reward_count]
        if reward_type == Challenge.BloodRewardType.NONE:
            payload["blood_reward_count"] = 0
        for field, value in payload.items():
            if field in {"contest_slug", "category"}:
                continue
            setattr(challenge, field, value)
        challenge.category = category
        challenge.updated_at = timezone.now()
        challenge.save()
        # 如果请求传入 tasks/attachments，则全量替换
        if "tasks" in payload:
            challenge.tasks.all().delete()  # type: ignore[attr-defined]
            self._sync_tasks(challenge, payload.get("tasks", []))  # type: ignore[attr-defined]
        if "attachments" in payload:
            challenge.attachments.all().delete()  # type: ignore[attr-defined]
            self._sync_attachments(challenge, payload.get("attachments", []))  # type: ignore[attr-defined]
        if "hints" in payload:
            challenge.hints.all().delete()  # type: ignore[attr-defined]
            self._sync_hints(challenge, payload.get("hints", []))  # type: ignore[attr-defined]
        logger.info(
            "更新题目",
            extra=logger_extra(
                {
                    "challenge": challenge.slug,
                    "contest": contest.slug,
                    "is_active": challenge.is_active,
                    "user_id": getattr(schema, "operator_id", None),
                }
            ),
        )
        broadcast_contest(
            contest.slug,
            {
                "event": "challenge_updated",
                "contest": contest.slug,
                "challenge": challenge.slug,
                "data": serialize_challenge_brief(challenge),
                "operator_id": getattr(schema, "operator_id", None),
            },
        )
        participants = list(self.participant_repo.filter(contest=contest, is_valid=True).select_related("user"))
        if participants:
            dedup = build_dedup_key(
                type=Notification.Type.CHALLENGE_UPDATED,
                contest=contest,
                challenge=challenge,
                bucket=challenge.updated_at.isoformat(timespec="minutes"),
            )
            fanout_notifications(
                [p.user for p in participants if getattr(p, "user", None)],
                type=Notification.Type.CHALLENGE_UPDATED,
                title=f"题目更新：{challenge.title}",
                body=contest.name,
                payload={
                    "contest": contest.slug,
                    "challenge": challenge.slug,
                },
                contest=contest,
                challenge=challenge,
                dedup_key=dedup,
            )
        return challenge
