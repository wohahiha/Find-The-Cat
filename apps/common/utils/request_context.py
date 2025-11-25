from __future__ import annotations

import contextvars
import uuid
from typing import Optional

request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")
user_id_ctx: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar("user_id", default=None)
username_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("username", default="")
path_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("path", default="")
method_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("method", default="")
ip_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("ip", default="")
ua_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("user_agent", default="")


def generate_request_id() -> str:
    return uuid.uuid4().hex[:12]


def set_request_context(
    *,
    request_id: Optional[str] = None,
    user_id: Optional[int] = None,
    username: str = "",
    path: str = "",
    method: str = "",
    ip: str = "",
    user_agent: str = "",
) -> None:
    request_id_ctx.set(request_id or generate_request_id())
    user_id_ctx.set(user_id)
    username_ctx.set(username or "")
    path_ctx.set(path or "")
    method_ctx.set(method or "")
    ip_ctx.set(ip or "")
    ua_ctx.set(user_agent or "")


def clear_request_context() -> None:
    request_id_ctx.set("")
    user_id_ctx.set(None)
    username_ctx.set("")
    path_ctx.set("")
    method_ctx.set("")
    ip_ctx.set("")
    ua_ctx.set("")


def get_request_context() -> dict:
    return {
        "request_id": request_id_ctx.get(""),
        "user_id": user_id_ctx.get(None),
        "username": username_ctx.get(""),
        "path": path_ctx.get(""),
        "method": method_ctx.get(""),
        "ip": ip_ctx.get(""),
        "user_agent": ua_ctx.get(""),
    }
