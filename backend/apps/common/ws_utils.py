# -*- coding: utf-8 -*-
"""
WebSocket 工具：封装 Channels 组广播，避免调用方关心 channel layer 细节
- 统一附带自增序号 seq，便于前端按序处理/去重
- 提供个人/比赛组广播与强制下线事件
"""

from __future__ import annotations

import itertools
import time

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.common.exceptions import CacheUnavailableError
from apps.common.infra import redis_client
from apps.common.infra.logger import get_logger, logger_extra
from apps.common.utils.redis_keys import ws_event_throttle_key

logger = get_logger(__name__)
_seq_generator = itertools.count(1)
_last_event_time: dict[str, float] = {}


def _safe_group_send(group: str, payload: dict) -> None:
    """
    安全发送组消息：没有 channel layer 时直接跳过，避免阻断业务
    """
    layer = get_channel_layer()
    if layer is None:
        return
    try:
        async_to_sync(layer.group_send)(group, {"type": "broadcast", **payload})
    except Exception:
        logger.warning(
            "WebSocket 广播失败，已忽略",
            extra=logger_extra({"group": group, "event": payload.get("event")}),
            exc_info=True,
        )


def allow_broadcast(key: str, *, interval_seconds: int) -> bool:
    """
    简单节流：同一 key 在 interval_seconds 内仅发送一次
    - 适用于高频事件（记分板片段、心跳广播等）
    """
    throttle_key = ws_event_throttle_key(key)
    try:
        # Redis 节流：存在则视为限流，设置带过期的标记
        if redis_client.get(throttle_key) is not None:
            return False
        redis_client.set(throttle_key, str(time.time()), ex=interval_seconds)
        return True
    except CacheUnavailableError:
        # Redis 不可用时退化为进程内节流，避免阻断业务
        pass
    now = time.time()
    last = _last_event_time.get(key, 0)
    if now - last < interval_seconds:
        return False
    _last_event_time[key] = now
    return True


def broadcast_notify(user_id: int, payload: dict) -> None:
    """向指定用户组广播事件"""
    payload = {"seq": next(_seq_generator), **payload}
    _safe_group_send(f"user_{user_id}", payload)


def broadcast_contest(contest_slug: str, payload: dict) -> None:
    """向比赛组广播事件"""
    payload = {"seq": next(_seq_generator), **payload}
    group_slug = contest_slug or "unknown"
    _safe_group_send(f"contest_{group_slug}", payload)


def broadcast_force_logout(user_id: int, *, reason: str | None = None) -> None:
    """
    强制下线事件：用于管理员封禁/权限变更后，通知前端断开并刷新
    """
    payload = {
        "event": "force_logout",
        "reason": reason or "权限变更或账号已被下线",
        "seq": next(_seq_generator),
    }
    _safe_group_send(f"user_{user_id}", payload)
