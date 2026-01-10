"""
题目模块的序列化工具函数：
- 业务场景：将模型对象转换为接口响应数据
- 模块角色：轻量 Presenter，视图层/服务层复用，避免重复手写字典
"""

from __future__ import annotations

from django.http import HttpRequest

from .models import Challenge, ChallengeHint, ChallengeCategory


def _full_url(url: str | None, request: HttpRequest | None) -> str | None:
    """将相对 URL 转为绝对 URL（若有 request），否则按原样返回"""
    if not url:
        return url
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if request:
        try:
            return request.build_absolute_uri(url)
        except Exception:
            return url
    return url


def serialize_hint(hint: ChallengeHint, *, unlocked: bool) -> dict:
    """提示序列化：未解锁时隐藏内容，仅返回基础信息与是否解锁"""
    return {
        "id": getattr(hint, "id", None),
        "title": hint.title,
        "content": hint.content if unlocked else "",
        "is_free": hint.is_free,
        "cost": hint.cost,
        "order": hint.order,
        "unlocked": unlocked,
    }


def serialize_category(category: ChallengeCategory) -> dict:
    """题目分类序列化：用于比赛详情/配置接口"""
    return {
        "id": getattr(category, "id", None),
        "contest": category.contest.slug if getattr(category, "contest_id", None) else None,
        "name": category.name,
        "slug": category.slug,
        "description": category.description,
    }


def serialize_challenge(
    challenge: Challenge,
    *,
    current_points: int | None = None,
    request: HttpRequest | None = None,
) -> dict:
    """
    题目序列化：包含基础信息、子任务、附件与提示概览（未解锁内容为空）
    - current_points：当前选手可获得的分值（含动态衰减与提示扣分），若为空则回退基础分
    - 业务场景：题目列表/详情、提交后返回题目得分视图
    """
    visible_points = current_points if current_points is not None else challenge.base_points
    has_machine = bool(getattr(challenge, "has_machine", False))
    return {
        "id": getattr(challenge, "id", None),
        "contest": getattr(challenge.contest, "slug", None),
        "title": challenge.title,
        "slug": challenge.slug,
        "short_description": challenge.short_description,
        "content": challenge.content,
        "category": challenge.category.name if challenge.category else None,
        "category_slug": challenge.category.slug if challenge.category else None,
        "difficulty": challenge.difficulty,
        "base_points": challenge.base_points,
        "current_points": visible_points,
        "flag_type": challenge.flag_type,
        "is_active": challenge.is_active,
        "has_machine": has_machine,
        "scoring_mode": challenge.scoring_mode,
        "decay_type": challenge.decay_type,
        "decay_factor": challenge.decay_factor,
        "min_score": challenge.min_score,
        "blood_reward_type": challenge.blood_reward_type,
        "blood_reward_count": challenge.blood_reward_count,
        "blood_bonus_points": challenge.blood_bonus_points,
        "tasks": [
            {
                "id": getattr(task, "id", None),
                "title": task.title,
                "description": task.description,
                "points": task.points,
                "order": task.order,
            }
            for task in getattr(challenge, "tasks", []).all().order_by("order", "id")  # type: ignore[attr-defined]
        ],
        "attachments": [
            {
                "id": getattr(att, "id", None),
                "name": att.name,
                "url": _full_url(att.url, request),
                "download_url": _full_url(att.url, request),
                "order": att.order,
            }
            for att in getattr(challenge, "attachments", []).all().order_by("order", "id")  # type: ignore[attr-defined]
        ],
        "hints": [
            {
                "id": getattr(hint, "id", None),
                "title": hint.title,
                "content": "",
                "is_free": hint.is_free,
                "cost": hint.cost,
                "order": hint.order,
                "unlocked": False,
            }
            for hint in getattr(challenge, "hints", []).all().order_by("order", "id")  # type: ignore[attr-defined]
        ],
    }
