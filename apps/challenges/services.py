# apps/challenges/services.py

from __future__ import annotations

from django.utils import timezone

from apps.common.base.base_service import BaseService
from apps.common.exceptions import (
    ConflictError,
    NotFoundError,
    ValidationError,
    WrongFlagError,
    ChallengeAlreadySolvedError,
    ChallengeNotAvailableError,
)
from apps.accounts.models import User
from apps.contests.repo import ContestRepo, TeamMemberRepo
from apps.contests.services import ContestContextService

from .models import Challenge, ChallengeSolve, ChallengeTask, ChallengeAttachment
from .repo import (
    ChallengeRepo,
    ChallengeCategoryRepo,
    ChallengeSolveRepo,
    ChallengeTaskRepo,
    ChallengeAttachmentRepo,
)
from .schemas import ChallengeCreateSchema, ChallengeUpdateSchema, ChallengeSubmitSchema

# 服务层：实现题目创建/更新、Flag 提交等业务流程，统一依赖仓储与 Schema。


def serialize_challenge(challenge: Challenge) -> dict:
    """题目序列化：包含基础信息、子任务与附件。"""
    return {
        "id": challenge.id,
        "contest": challenge.contest.slug,
        "title": challenge.title,
        "slug": challenge.slug,
        "short_description": challenge.short_description,
        "content": challenge.content,
        "category": challenge.category.name if challenge.category else None,
        "difficulty": challenge.difficulty,
        "base_points": challenge.base_points,
        "flag_type": challenge.flag_type,
        "is_active": challenge.is_active,
        "tasks": [
            {
                "id": task.id,
                "title": task.title,
                "description": task.description,
                "points": task.points,
                "order": task.order,
            }
            for task in challenge.tasks.all().order_by("order", "id")
        ],
        "attachments": [
            {
                "id": att.id,
                "name": att.name,
                "url": att.url,
                "order": att.order,
            }
            for att in challenge.attachments.all().order_by("order", "id")
        ],
    }


class ChallengeCreateService(BaseService[Challenge]):
    """
    创建题目服务：
    - 校验并创建题目，同时写入子任务与附件。
    - 自动处理分类与作者关联。
    """
    def __init__(
        self,
        contest_repo: ContestRepo | None = None,
        challenge_repo: ChallengeRepo | None = None,
        category_repo: ChallengeCategoryRepo | None = None,
        task_repo: ChallengeTaskRepo | None = None,
        attachment_repo: ChallengeAttachmentRepo | None = None,
    ):
        self.contest_repo = contest_repo or ContestRepo()
        self.challenge_repo = challenge_repo or ChallengeRepo()
        self.category_repo = category_repo or ChallengeCategoryRepo()
        self.task_repo = task_repo or ChallengeTaskRepo()
        self.attachment_repo = attachment_repo or ChallengeAttachmentRepo()

    def perform(self, user: User, schema: ChallengeCreateSchema) -> Challenge:
        # 1) 获取比赛与分类（可选创建）
        contest = self.contest_repo.get_by_slug(schema.contest_slug)
        category = None
        if schema.category:
            category = self.category_repo.get_or_create_slug(schema.category)
        # 2) 准备 payload 并剥离子任务/附件
        payload = schema.to_dict(exclude_none=True)
        payload.pop("contest_slug", None)
        payload.update({"contest": contest, "category": category, "author": user})
        tasks = payload.pop("tasks", [])
        attachments = payload.pop("attachments", [])
        # 3) 创建题目并同步子任务与附件
        challenge = self.challenge_repo.create(payload)
        self._sync_tasks(challenge, tasks)
        self._sync_attachments(challenge, attachments)
        return challenge

    def _sync_tasks(self, challenge: Challenge, tasks_data: list) -> None:
        """创建子任务列表。"""
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
        """创建附件列表。"""
        for idx, att in enumerate(attachments_data, start=1):
            self.attachment_repo.create(
                {
                    "challenge": challenge,
                    "name": att.get("name", f"附件{idx}"),
                    "url": att.get("url", ""),
                    "order": int(att.get("order", idx)),
                }
            )


class ChallengeUpdateService(BaseService[Challenge]):
    def __init__(
        self,
        contest_repo: ContestRepo | None = None,
        challenge_repo: ChallengeRepo | None = None,
        category_repo: ChallengeCategoryRepo | None = None,
        task_repo: ChallengeTaskRepo | None = None,
        attachment_repo: ChallengeAttachmentRepo | None = None,
    ):
        self.contest_repo = contest_repo or ContestRepo()
        self.challenge_repo = challenge_repo or ChallengeRepo()
        self.category_repo = category_repo or ChallengeCategoryRepo()
        self.task_repo = task_repo or ChallengeTaskRepo()
        self.attachment_repo = attachment_repo or ChallengeAttachmentRepo()

    def perform(self, schema: ChallengeUpdateSchema) -> Challenge:
        # 1) 获取比赛与题目
        contest = self.contest_repo.get_by_slug(schema.contest_slug)
        challenge = self.challenge_repo.get_by_slug(contest=contest, slug=schema.slug)
        # 2) 处理分类
        category = challenge.category
        if schema.category:
            category = self.category_repo.get_or_create_slug(schema.category)
        # 3) 更新字段并保存
        payload = schema.to_dict(exclude_none=True)
        payload.pop("contest_slug", None)
        for field, value in payload.items():
            if field in {"contest_slug", "category"}:
                continue
            setattr(challenge, field, value)
        challenge.category = category
        challenge.updated_at = timezone.now()
        challenge.save()
        # 如果请求传入 tasks/attachments，则全量替换
        if "tasks" in payload:
            # 先删除旧子任务再重建
            challenge.tasks.all().delete()
            self._sync_tasks(challenge, payload.get("tasks", []))
        if "attachments" in payload:
            # 先删除旧附件再重建
            challenge.attachments.all().delete()
            self._sync_attachments(challenge, payload.get("attachments", []))
        return challenge

    def _sync_tasks(self, challenge: Challenge, tasks_data: list) -> None:
        for idx, task in enumerate(tasks_data, start=1):
            ChallengeTaskRepo().create(
                {
                    "challenge": challenge,
                    "title": task.get("title", ""),
                    "description": task.get("description", ""),
                    "points": int(task.get("points", 0)),
                    "order": int(task.get("order", idx)),
                }
            )

    def _sync_attachments(self, challenge: Challenge, attachments_data: list) -> None:
        for idx, att in enumerate(attachments_data, start=1):
            ChallengeAttachmentRepo().create(
                {
                    "challenge": challenge,
                    "name": att.get("name", f"附件{idx}"),
                    "url": att.get("url", ""),
                    "order": int(att.get("order", idx)),
                }
            )


class ChallengeSubmitService(BaseService[ChallengeSolve]):
    """
    提交 Flag 服务：
    - 校验比赛状态、题目开放性。
    - 校验 Flag，防重复提交，记录得分。
    """
    def __init__(
        self,
        challenge_repo: ChallengeRepo | None = None,
        contest_service: ContestContextService | None = None,
        solve_repo: ChallengeSolveRepo | None = None,
        team_member_repo: TeamMemberRepo | None = None,
    ):
        self.challenge_repo = challenge_repo or ChallengeRepo()
        self.context_service = contest_service or ContestContextService()
        self.solve_repo = solve_repo or ChallengeSolveRepo()
        self.team_member_repo = team_member_repo or TeamMemberRepo()

    def perform(self, user: User, *, contest_slug: str, challenge_slug: str, schema: ChallengeSubmitSchema) -> ChallengeSolve:
        # 1) 校验比赛进行中
        contest = self.context_service.get_contest(contest_slug)
        self.context_service.ensure_contest_running(contest)

        # 2) 获取题目并确认开放
        challenge = self.challenge_repo.get_by_slug(contest=contest, slug=challenge_slug)
        if not challenge.is_active:
            raise ChallengeNotAvailableError(message="题目未开放")

        # 3) 校验 Flag
        if not challenge.check_flag(schema.flag):
            raise WrongFlagError(message="Flag 不正确")

        # 4) 防重复提交
        existing = self.solve_repo.get_user_solve(challenge=challenge, user=user)
        if existing:
            raise ChallengeAlreadySolvedError(message="你已经解出该题目")

        # 5) 获取队伍关系并记录得分
        membership = self.team_member_repo.get_membership(contest=contest, user=user)
        awarded_points = challenge.base_points
        solve = self.solve_repo.create(
            {
                "challenge": challenge,
                "user": user,
                "team": membership.team if membership else None,
                "awarded_points": awarded_points,
            }
        )
        return solve
