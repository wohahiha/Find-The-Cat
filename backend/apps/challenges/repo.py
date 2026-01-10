# apps/challenges/repo.py

from __future__ import annotations

from typing import Any, Optional
from django.db import models
from django.db.models import Prefetch, QuerySet

from django.utils.text import slugify

from apps.common.base.base_repo import BaseRepo
from apps.common.exceptions import NotFoundError

from .models import (
    Challenge,
    ChallengeCategory,
    ChallengeSolve,
    ChallengeTask,
    ChallengeAttachment,
    ChallengeHint,
    ChallengeHintUnlock,
)
from apps.contests.models import Contest
from apps.accounts.models import User


# 仓储层：封装题目、分类、解题、子任务/附件/提示的数据库访问，供服务层复用


class ChallengeCategoryRepo(BaseRepo[ChallengeCategory]):
    """
    题目分类仓储：
    - 业务场景：按比赛维护题目分类，供题目创建选择
    - 功能：支持按名称/slug 获取、按比赛批量同步
    """

    model = ChallengeCategory

    def list_by_contest(self, contest: Contest):
        """返回比赛下的全部题目分类"""
        return (
            self.filter(contest=contest)
            .select_related("contest")
            .order_by("name", "id")
        )

    def resolve_for_contest(self, contest: Contest, value: str) -> Optional[ChallengeCategory]:
        """根据名称或 slug 获取比赛内的分类"""
        if not value:
            return None
        slug = slugify(value) or value.lower()
        return (
            self.filter(contest=contest)
            .filter(models.Q(slug=slug) | models.Q(name=value) | models.Q(name__iexact=value))
            .first()
        )

    def sync_for_contest(self, contest: Contest, categories: list[str]) -> list[ChallengeCategory]:
        """
        批量同步题目分类：
        - 未在列表中的旧分类将删除
        - 新名称将创建
        """
        normalized: list[tuple[str, str]] = []
        seen_slug: set[str] = set()
        for name in categories or []:
            clean_name = str(name).strip()
            if not clean_name:
                continue
            slug = slugify(clean_name) or clean_name.lower()
            if slug in seen_slug:
                continue
            seen_slug.add(slug)
            normalized.append((clean_name, slug))

        existing = {
            cat.slug: cat
            for cat in self.filter(contest=contest).select_related("contest")
        }
        retained_ids: list[int] = []
        results: list[ChallengeCategory] = []
        for name, slug in normalized:
            if slug in existing:
                cat = existing[slug]
                if cat.name != name:
                    cat.name = name
                    cat.save(update_fields=["name"])
                retained_ids.append(getattr(cat, "id", 0))
                results.append(cat)
                continue
            cat = self.create(
                {
                    "contest": contest,
                    "name": name,
                    "slug": slug,
                }
            )
            retained_ids.append(getattr(cat, "id", 0))
            results.append(cat)

        # 删除未保留的分类
        if retained_ids:
            self.filter(contest=contest).exclude(id__in=retained_ids).delete()
        else:
            self.filter(contest=contest).delete()
        return results


class ChallengeRepo(BaseRepo[Challenge]):
    """
    题目仓储：
    - 业务场景：列表/详情/提交等按比赛 + slug 获取题目
    - 功能：封装获取逻辑，若不存在抛业务级 NotFoundError
    """
    model = Challenge

    def get_by_slug(self, *, contest: Contest, slug: str) -> Challenge:
        # 查询题目，不存在时抛出业务级 404
        try:
            return (
                self.filter(contest=contest, slug=slug)
                .select_related("contest", "category", "author", "machine_config")
                .prefetch_related(
                    Prefetch("tasks", queryset=ChallengeTask.objects.order_by("order", "id")),
                    Prefetch("attachments", queryset=ChallengeAttachment.objects.order_by("order", "id")),
                    Prefetch("hints", queryset=ChallengeHint.objects.order_by("order", "id")),
                )
                .get()
            )
        except Challenge.DoesNotExist as exc:  # type: ignore[attr-defined]
            raise NotFoundError(message="题目不存在") from exc

    def list_active_with_related(self, *, contest: Contest):
        """
        列出比赛下已开放题目，带上关联对象，减少 N+1
        """
        return (
            self.filter(contest=contest, is_active=True)
            .select_related("contest", "category", "author", "machine_config")
            .prefetch_related(
                Prefetch("tasks", queryset=ChallengeTask.objects.order_by("order", "id")),
                Prefetch("attachments", queryset=ChallengeAttachment.objects.order_by("order", "id")),
                Prefetch("hints", queryset=ChallengeHint.objects.order_by("order", "id")),
            )
        )


class ChallengeSolveRepo(BaseRepo[ChallengeSolve]):
    """
    解题记录仓储：
    - 业务场景：判题/榜单统计时需要判断用户/队伍是否已解出
    - 功能：提供按题目+用户获取解题记录的便捷方法
    """
    model = ChallengeSolve

    def get_user_solve(self, *, challenge: Challenge, user: User) -> Optional[ChallengeSolve]:
        # 返回用户的解题记录，若不存在则 None
        return self.filter(challenge=challenge, user=user).first()

    def get_user_solve_with_related(self, *, challenge: Challenge, user: User) -> Optional[ChallengeSolve]:
        """带外键的解题记录，减少后续访问 N+1"""
        return (
            self.filter(challenge=challenge, user=user)
            .select_related("challenge", "user", "team")
            .first()
        )


class ChallengeTaskRepo(BaseRepo[ChallengeTask]):
    """题目子任务仓储：管理子任务的 CRUD，供题目创建/更新同步"""

    model = ChallengeTask


class ChallengeAttachmentRepo(BaseRepo[ChallengeAttachment]):
    """题目附件仓储：管理附件的 CRUD，供题目创建/更新同步"""

    model = ChallengeAttachment


class ChallengeHintRepo(BaseRepo[ChallengeHint]):
    """
    题目提示仓储：
    - 业务场景：提示列表、解锁校验
    - 功能：按题目获取提示列表、按 ID 获取提示
    """

    model = ChallengeHint

    def list_for_challenge(self, challenge: Challenge):
        return self.filter(challenge=challenge).order_by("order", "id")

    def get_by_id(self, pk: Any, *, queryset: Optional[QuerySet[ChallengeHint]] = None) -> ChallengeHint:
        try:
            qs = queryset or self.get_queryset()
            return qs.get(pk=pk)
        except ChallengeHint.DoesNotExist as exc:  # type: ignore[attr-defined]
            raise NotFoundError(message="提示不存在") from exc


class ChallengeHintUnlockRepo(BaseRepo[ChallengeHintUnlock]):
    """
    提示解锁记录仓储：
    - 业务场景：提示解锁、扣分统计、榜单扣分
    - 功能：查询是否已解锁、创建解锁记录、统计扣分成本
    """

    model = ChallengeHintUnlock

    def has_unlocked(self, *, hint: ChallengeHint, user: User, team=None) -> bool:
        """判断用户或队伍是否已解锁指定提示（队伍/个人）"""
        qs = self.filter(hint=hint)
        if team and qs.filter(team=team).exists():
            return True
        return qs.filter(user=user).exists()

    def create_unlock(self, *, hint: ChallengeHint, challenge: Challenge, user: User, team=None, cost: int = 0):
        """创建解锁记录，带上队伍/成本信息"""
        return self.create(
            {
                "hint": hint,
                "challenge": challenge,
                "user": user,
                "team": team,
                "cost": cost,
            }
        )

    def total_cost(self, *, challenge_ids: list[int], user_ids: list[int] | None = None,
                   team_ids: list[int] | None = None) -> dict[str, int]:
        """
        统计提示扣分：
        - 返回以 user/team 维度的总成本，用于榜单扣减
        """
        qs = self.filter(challenge_id__in=challenge_ids)
        if user_ids is not None:
            qs = qs.filter(user_id__in=user_ids)
        if team_ids is not None:
            qs = qs.filter(team_id__in=team_ids)
        costs: dict[str, int] = {}
        for rec in qs.values("user_id", "team_id", "cost"):
            key = f"team-{rec['team_id']}" if rec["team_id"] else f"user-{rec['user_id']}"
            costs[key] = costs.get(key, 0) + int(rec["cost"] or 0)
        return costs

    def cost_for_solver(self, *, challenge: Challenge, user: User, team=None) -> int:
        """当前用户/队伍在指定题目的总提示成本，供计分扣减使用"""
        qs = self.filter(challenge=challenge)
        if team:
            qs = qs.filter(models.Q(team=team) | models.Q(user=user))
        else:
            qs = qs.filter(user=user)
        return sum(int(item.cost or 0) for item in qs)
