# -*- coding: utf-8 -*-
"""
通用 WebSocket 消费者

功能目标：
- 轻量级实时通知，不做持久化/历史消息
- 支持按比赛 slug 分组推送（便于记分板/公告刷新）
- 复用现有 RBAC：连接时校验登录与业务权限
"""

from __future__ import annotations

import asyncio
import time

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from django.conf import settings

from apps.common.permissions import has_biz_permission
from apps.system.services import ConfigService
from apps.common.exceptions import CacheUnavailableError
from apps.common.infra import redis_client
from apps.common.utils.redis_keys import ws_user_conn_key, ws_ip_conn_key

# 连接配额统计（单进程）：限制用户/IP 并发连接，避免滥用
_user_conn_count: dict[int, int] = {}
_ip_conn_count: dict[str, int] = {}
_CONNECTION_TTL_SECONDS = 3600  # Redis 计数键过期时间，防止异常断开留下脏值


def _client_ip(scope) -> str:
    """从 scope 提取客户端 IP"""
    client = scope.get("client") or ()
    if isinstance(client, (list, tuple)) and client:
        return client[0] or ""
    return ""


def _register_connection(user_id: int, ip: str) -> bool:
    """注册连接计数，超过阈值返回 False，优先使用 Redis 计数"""
    cfg = ConfigService()
    max_user = int(cfg.get("WS_MAX_CONNECTIONS_PER_USER", getattr(settings, "WS_MAX_CONNECTIONS_PER_USER", 5)) or 5)
    max_ip = int(cfg.get("WS_MAX_CONNECTIONS_PER_IP", getattr(settings, "WS_MAX_CONNECTIONS_PER_IP", 20)) or 20)
    try:
        user_key = ws_user_conn_key(user_id)
        user_count = redis_client.incr(user_key, amount=1, ex=_CONNECTION_TTL_SECONDS)
        ip_count = 0
        if ip:
            ip_key = ws_ip_conn_key(ip)
            ip_count = redis_client.incr(ip_key, amount=1, ex=_CONNECTION_TTL_SECONDS)
        if (0 < max_user <= user_count) or (ip and 0 < max_ip <= ip_count):
            _unregister_connection(user_id, ip)  # 回滚计数
            return False
        return True
    except CacheUnavailableError:
        # Redis 不可用时回退为进程内计数，避免阻断连接
        current_user = _user_conn_count.get(user_id, 0)
        current_ip = _ip_conn_count.get(ip, 0)
        if (0 < max_user <= current_user) or (ip and 0 < max_ip <= current_ip):
            return False
        _user_conn_count[user_id] = current_user + 1
        if ip:
            _ip_conn_count[ip] = current_ip + 1
        return True


def _unregister_connection(user_id: int, ip: str) -> None:
    """连接关闭后递减计数，兼容 Redis 与进程内回退"""
    try:
        user_val = redis_client.incr(ws_user_conn_key(user_id), amount=-1, ex=_CONNECTION_TTL_SECONDS)
        if user_val is not None and user_val < 0:
            redis_client.set(ws_user_conn_key(user_id), 0, ex=_CONNECTION_TTL_SECONDS)
        if ip:
            ip_val = redis_client.incr(ws_ip_conn_key(ip), amount=-1, ex=_CONNECTION_TTL_SECONDS)
            if ip_val is not None and ip_val < 0:
                redis_client.set(ws_ip_conn_key(ip), 0, ex=_CONNECTION_TTL_SECONDS)
        return
    except CacheUnavailableError:
        pass
    if user_id in _user_conn_count:
        _user_conn_count[user_id] = max(0, _user_conn_count[user_id] - 1)
    if ip and ip in _ip_conn_count:
        _ip_conn_count[ip] = max(0, _ip_conn_count[ip] - 1)


class BaseAuthorizedConsumer(AsyncJsonWebsocketConsumer):
    """
    带业务权限校验的基础 Consumer
    """

    required_perm: str | None = None  # 可在子类覆盖或根据路径参数动态计算
    heartbeat_timeout_seconds: int = 120  # 超时自动断开
    heartbeat_interval_seconds: int = 25  # 与前端 ping 周期相近
    client_ip: str = ""
    _last_ping: float = 0.0
    _monitor_task: asyncio.Task | None = None

    async def connect(self):
        user = self.scope.get("user")
        if user is None or isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close(code=4401)
            return
        if self.required_perm and not has_biz_permission(user, self.required_perm):
            await self.close(code=4403)
            return
        self.client_ip = _client_ip(self.scope)
        if not _register_connection(user.id, self.client_ip):
            await self.close(code=4429)
            return
        self._last_ping = time.time()
        self._monitor_task = asyncio.create_task(self._monitor_heartbeat())
        await self.accept()
        return

    async def disconnect(self, close_code):
        # 子类如有 group 需在此处 group_discard
        user = self.scope.get("user")
        if user and getattr(user, "id", None):
            _unregister_connection(user.id, getattr(self, "client_ip", ""))
        if getattr(self, "_monitor_task", None):
            self._monitor_task.cancel()
        return None

    async def receive_json(self, content, **kwargs):
        """
        统一处理心跳：
        - 前端发送 {"type":"ping"}，返回 {"event":"pong"} 并更新最后活跃时间
        - 其他消息由子类继续处理
        """
        msg_type = content.get("type")
        if msg_type == "ping":
            self._last_ping = time.time()
            await self.send_json({"event": "pong", "ts": self._last_ping})
            return None

        return await super().receive_json(content, **kwargs)

    async def _monitor_heartbeat(self):
        """后台心跳监控：若长时间未收到 ping 则自动断开"""
        try:
            while True:
                # 刷新连接计数 TTL，避免长连导致计数过期
                try:
                    user = getattr(self.scope.get("user"), "id", None)
                    if user:
                        redis_client.incr(ws_user_conn_key(user), amount=0, ex=_CONNECTION_TTL_SECONDS)
                    if getattr(self, "client_ip", ""):
                        redis_client.incr(ws_ip_conn_key(self.client_ip), amount=0, ex=_CONNECTION_TTL_SECONDS)
                except CacheUnavailableError:
                    pass
                await asyncio.sleep(self.heartbeat_interval_seconds)
                now = time.time()
                if now - getattr(self, "_last_ping", now) > self.heartbeat_timeout_seconds:
                    await self.close(code=4410)
                    break
        except asyncio.CancelledError:
            return None


class NotifyConsumer(BaseAuthorizedConsumer):
    """
    通用通知通道：
    - 需登录（可根据业务码扩展）
    - 默认加入个人频道，便于点对点推送
    """

    required_perm = None  # 登录即可
    user_group: str | None = None

    async def connect(self):
        user = self.scope.get("user")
        if user is None or isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close(code=4401)
            return None
        await self.accept()
        self.user_group = f"user_{user.id}"
        if self.channel_layer:
            await self.channel_layer.group_add(self.user_group, self.channel_name)
        return None

    async def disconnect(self, close_code):
        if getattr(self, "user_group", None) and self.channel_layer:
            await self.channel_layer.group_discard(self.user_group, self.channel_name)
        return None

    async def broadcast(self, event):
        """统一的广播入口：直接把 event 透传给前端"""
        await self.send_json(event)


class ContestEventConsumer(BaseAuthorizedConsumer):
    """
    比赛事件通道：
    - 登录且具备查看比赛权限即可加入
    - 按比赛 slug 进行分组推送，便于记分板/公告刷新
    """

    required_perm = "contests.view_contest"
    contest_slug: str | None = None
    group_name: str | None = None

    async def connect(self):
        user = self.scope.get("user")
        if user is None or isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close(code=4401)
            return None
        if not has_biz_permission(user, self.required_perm):
            await self.close(code=4403)
            return None
        self.contest_slug = self.scope["url_route"]["kwargs"].get("contest_slug")
        safe_slug = self.contest_slug or "unknown"
        self.group_name = f"contest_{safe_slug}"
        await self.accept()
        if self.channel_layer:
            await self.channel_layer.group_add(self.group_name, self.channel_name)
        return None

    async def disconnect(self, close_code):
        if getattr(self, "group_name", None) and self.channel_layer:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        return None

    async def broadcast(self, event):
        """统一广播入口：透传事件数据"""
        await self.send_json(event)
