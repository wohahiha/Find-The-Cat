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


def ws_user_conn_key(user_id: int) -> str:
    """WebSocket 用户并发连接计数键"""
    return f"ws:user:{user_id}:connections"


def ws_ip_conn_key(ip: str) -> str:
    """WebSocket IP 并发连接计数键"""
    return f"ws:ip:{ip}:connections"


def ws_event_throttle_key(key: str) -> str:
    """WebSocket 事件节流键"""
    return f"ws:event:{key}:throttle"


def email_code_fail_key(email: str, scene: str) -> str:
    """邮箱验证码校验失败计数键"""
    return f"email_code:{scene}:{email}:fail"


def login_fail_user_key(identifier: str) -> str:
    """登录失败计数（按用户名/邮箱）"""
    return f"login_fail:user:{identifier}"


def login_fail_ip_key(ip: str) -> str:
    """登录失败计数（按 IP）"""
    return f"login_fail:ip:{ip}"
