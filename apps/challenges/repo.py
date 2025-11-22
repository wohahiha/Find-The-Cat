# apps/challenges/repo.py

from __future__ import annotations

from typing import Optional

from django.utils.text import slugify

from apps.common.base.base_repo import BaseRepo
from apps.common.exceptions import NotFoundError

from .models import Challenge, ChallengeCategory, ChallengeSolve, ChallengeTask, ChallengeAttachment
from apps.contests.models import Contest
from apps.accounts.models import User

# 仓储层：封装题目、分类、解题、子任务与附件的数据库访问，供服务层复用。


class ChallengeCategoryRepo(BaseRepo[ChallengeCategory]):
    """题目分类仓储：支持通过名称生成 slug 并获取/创建分类。"""
    model = ChallengeCategory

    def get_or_create_slug(self, name: str) -> ChallengeCategory:
        # 基于名称生成 slug 并尝试获取，不存在则创建
        slug = slugify(name) or name.lower()
        obj, _ = self.model.objects.get_or_create(slug=slug, defaults={"name": name})
        return obj


class ChallengeRepo(BaseRepo[Challenge]):
    """题目仓储：提供按比赛 + slug 获取题目的便捷方法。"""
    model = Challenge

    def get_by_slug(self, *, contest: Contest, slug: str) -> Challenge:
        # 查询题目，不存在时抛出业务级 404
        try:
            return self.filter(contest=contest, slug=slug).get()
        except Challenge.DoesNotExist as exc:  # type: ignore[attr-defined]
            raise NotFoundError(message="题目不存在") from exc


class ChallengeSolveRepo(BaseRepo[ChallengeSolve]):
    """解题记录仓储：查询用户是否已解出该题。"""
    model = ChallengeSolve

    def get_user_solve(self, *, challenge: Challenge, user: User) -> Optional[ChallengeSolve]:
        # 返回用户的解题记录，若不存在则 None
        return self.filter(challenge=challenge, user=user).first()


class ChallengeTaskRepo(BaseRepo[ChallengeTask]):
    """题目子任务仓储：管理子任务的 CRUD。"""

    model = ChallengeTask


class ChallengeAttachmentRepo(BaseRepo[ChallengeAttachment]):
    """题目附件仓储：管理附件的 CRUD。"""

    model = ChallengeAttachment
