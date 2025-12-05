"""
JWT 工具封装：颁发与校验访问/刷新令牌

- 依赖 SimpleJWT，在 accounts 服务层或测试中可直接调用 issue_tokens
- 仅封装常用场景，减少各处重复调用 RefreshToken API
 - 业务场景：登录/刷新时颁发令牌，接口鉴权时校验 access token
"""

from __future__ import annotations

from typing import Any, Dict

from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken, TokenError as SimpleJWTError

from apps.common.exceptions import AuthError

User = get_user_model()


def issue_tokens(user: Any) -> Dict[str, str]:
    """
    为指定用户颁发 refresh/access 令牌
    """
    try:
        refresh = RefreshToken.for_user(user)
    except Exception as exc:  # pragma: no cover - SimpleJWT 内部异常
        raise AuthError(message="颁发令牌失败") from exc
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


def refresh_access(refresh_token: str) -> Dict[str, str]:
    """
    使用 refresh_token 刷新获取新的 access_token
    """
    try:
        refresh = RefreshToken(refresh_token)
        access = refresh.access_token
    except SimpleJWTError as exc:
        raise AuthError(message="刷新令牌无效或已过期") from exc
    return {"refresh": str(refresh), "access": str(access)}


def verify_access(token: str) -> AccessToken:
    """
    校验 access token 并返回 AccessToken 对象，失败抛 AuthError
    """
    try:
        return AccessToken(token)
    except SimpleJWTError as exc:
        raise AuthError(message="访问令牌无效或已过期") from exc
