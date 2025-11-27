# apps/common/utils/redis_keys.py

from __future__ import annotations

"""
Redis 键名集中管理，避免各模块随意拼接带来不一致
业务场景：记分板缓存、血次序计数、靶机端口占用等公用键
"""


def scoreboard_key(contest_id: int) -> str:
    """记分板缓存键"""
    return f"contest:{contest_id}:scoreboard"


def blood_rank_key(challenge_id: int) -> str:
    """题目血次序计数器键"""
    return f"challenge:{challenge_id}:blood_rank"


def machine_ports_key() -> str:
    """靶机占用端口集合键"""
    return "machines:ports:used"
