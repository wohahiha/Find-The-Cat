"""
题目模块的序列化工具函数：
- 业务场景：将模型对象转换为接口响应数据。
- 模块角色：轻量 Presenter，视图层/服务层复用，避免重复手写字典。
"""

from __future__ import annotations

from .models import Challenge, ChallengeHint


def serialize_hint(hint: ChallengeHint, *, unlocked: bool) -> dict:
    """提示序列化：未解锁时隐藏内容，仅返回基础信息与是否解锁。"""
    return {
        "id": hint.id,
        "title": hint.title,
        "content": hint.content if unlocked or hint.is_free else "",
        "is_free": hint.is_free,
        "cost": hint.cost,
        "order": hint.order,
        "unlocked": unlocked or hint.is_free,
    }


def serialize_challenge(challenge: Challenge, *, current_points: int | None = None) -> dict:
    """
    题目序列化：包含基础信息、子任务、附件与提示概览（未解锁内容为空）。
    - current_points：当前选手可获得的分值（含动态衰减与提示扣分），若为空则回退基础分。
    - 业务场景：题目列表/详情、提交后返回题目得分视图。
    """
    visible_points = current_points if current_points is not None else challenge.base_points
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
        "current_points": visible_points,
        "flag_type": challenge.flag_type,
        "is_active": challenge.is_active,
        "scoring_mode": challenge.scoring_mode,
        "decay_type": challenge.decay_type,
        "decay_factor": challenge.decay_factor,
        "min_score": challenge.min_score,
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
        "hints": [
            {
                "id": hint.id,
                "title": hint.title,
                "content": "",
                "is_free": hint.is_free,
                "cost": hint.cost,
                "order": hint.order,
                "unlocked": False,
            }
            for hint in challenge.hints.all().order_by("order", "id")
        ],
    }
