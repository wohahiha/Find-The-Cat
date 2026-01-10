from __future__ import annotations

import contextvars
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")
user_id_ctx: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar("user_id", default=None)
account_id_ctx: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar("account_id", default=None)
username_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("username", default="")
path_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("path", default="")
method_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("method", default="")
ip_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("ip", default="")
ua_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("user_agent", default="")
last_context_ctx: contextvars.ContextVar[dict | None] = contextvars.ContextVar("last_context", default=None)
last_context_expire_ctx: contextvars.ContextVar[Optional[datetime]] = contextvars.ContextVar(
    "last_context_expire", default=None
)
LAST_CONTEXT_TTL = timedelta(seconds=2)


def generate_request_id() -> str:
    return uuid.uuid4().hex[:12]


def set_request_context(
    *,
    request_id: Optional[str] = None,
    user_id: Optional[int] = None,
    account_id: Optional[int] = None,
    username: str = "",
    path: str = "",
    method: str = "",
    ip: str = "",
    user_agent: str = "",
) -> None:
    request_id_ctx.set(request_id or generate_request_id())
    user_id_ctx.set(user_id)
    account_id_ctx.set(account_id)
    username_ctx.set(username or "")
    path_ctx.set(path or "")
    method_ctx.set(method or "")
    ip_ctx.set(ip or "")
    ua_ctx.set(user_agent or "")


def clear_request_context() -> None:
    # 在清空当前上下文前，先记录快照，供日志在请求结束后的最后阶段读取
    snapshot = {
        "request_id": request_id_ctx.get(""),
        "user_id": user_id_ctx.get(None),
        "account_id": account_id_ctx.get(None),
        "username": username_ctx.get(""),
        "path": path_ctx.get(""),
        "method": method_ctx.get(""),
        "ip": ip_ctx.get(""),
        "user_agent": ua_ctx.get(""),
    }
    if snapshot["request_id"]:
        last_context_ctx.set(snapshot)
        last_context_expire_ctx.set(datetime.now(timezone.utc) + LAST_CONTEXT_TTL)
    request_id_ctx.set("")
    user_id_ctx.set(None)
    account_id_ctx.set(None)
    username_ctx.set("")
    path_ctx.set("")
    method_ctx.set("")
    ip_ctx.set("")
    ua_ctx.set("")


def get_request_context() -> dict:
    ctx = {
        "request_id": request_id_ctx.get(""),
        "user_id": user_id_ctx.get(None),
        "account_id": account_id_ctx.get(None),
        "username": username_ctx.get(""),
        "path": path_ctx.get(""),
        "method": method_ctx.get(""),
        "ip": ip_ctx.get(""),
        "user_agent": ua_ctx.get(""),
    }
    if not ctx["request_id"]:
        last_ctx = last_context_ctx.get(None)
        expire_at = last_context_expire_ctx.get(None)
        if last_ctx and expire_at and expire_at > datetime.now(timezone.utc):
            return last_ctx
    return ctx


def update_request_user(user) -> None:
    """
    在认证完成后更新当前请求上下文中的用户信息

    适用于 DRF 认证流程（如 JWT），因为中间件执行时 request.user 还未就绪。
    """
    current = get_request_context()
    set_request_context(
        request_id=current.get("request_id") or generate_request_id(),
        user_id=getattr(user, "id", None),
        account_id=getattr(user, "account_id", None),
        username=getattr(user, "username", "") or "",
        path=current.get("path", ""),
        method=current.get("method", ""),
        ip=current.get("ip", ""),
        user_agent=current.get("user_agent", ""),
    )
