# -*- coding: utf-8 -*-
"""
WebSocket JWT 鉴权中间件

作用：
- 解析 WebSocket 握手中的 Authorization 头（Bearer Token）或 query 参数 token
- 验证 SimpleJWT access token，注入 scope["user"]，与现有 RBAC 校验衔接
"""

from __future__ import annotations

from typing import Optional
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from apps.common.infra.jwt_provider import verify_access

User = get_user_model()


@database_sync_to_async
def _get_user(user_id: int) -> Optional[User]:
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return None


class JWTAuthMiddleware(BaseMiddleware):
    """
    WebSocket JWT 认证中间件
    - 优先解析 Authorization: Bearer <token>
    - 兼容 querystring 中的 token=<token>
    """

    async def __call__(self, scope, receive, send):
        headers = dict(scope.get("headers") or [])
        token = None

        auth_header = headers.get(b"authorization", b"").decode()
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()
        if not token:
            query_string = scope.get("query_string", b"").decode()
            params = parse_qs(query_string)
            token = params.get("token", [None])[0]

        user = AnonymousUser()
        if token:
            try:
                access = verify_access(token)
                user_id = access.get("user_id")
                if user_id:
                    db_user = await _get_user(user_id)
                    if db_user:
                        user = db_user
            except Exception:
                user = AnonymousUser()

        scope["user"] = user
        return await super().__call__(scope, receive, send)
