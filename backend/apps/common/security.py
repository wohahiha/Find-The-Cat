"""
安全事件日志工具
- 统一记录登录/验证码等敏感操作的安全日志，便于审计
"""

from __future__ import annotations

from typing import Any, Optional
from django.http import HttpRequest

from apps.common.infra.logger import get_logger, logger_extra

security_logger = get_logger("apps.security")


def _get_client_ip(request: HttpRequest) -> str:
    """
    获取客户端 IP（优先 X-Forwarded-For）
    """
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def log_security_event(
    *,
    action: str,
    request: HttpRequest,
    username: Optional[str] = None,
    user_id: Optional[int] = None,
    detail: Optional[str] = None,
    extra_fields: Optional[dict[str, Any]] = None,
) -> None:
    """
    记录安全事件日志
    - action: 事件类型（login_success/login_failed/send_email_code 等）
    - request: 当前请求对象，用于提取 IP、path、request_id
    - username/user_id: 涉及的用户标识
    - detail: 补充信息
    - extra_fields: 额外字段（如场景/邮箱等）
    """
    extra = {
        "action": action,
        "username": username,
        "user_id": user_id,
        "ip": _get_client_ip(request),
        "path": request.path,
        "request_id": getattr(request, "request_id", None),
    }
    if detail:
        extra["detail"] = detail
    if extra_fields:
        extra.update(extra_fields)
    security_logger.info("安全事件", extra=logger_extra(extra))
