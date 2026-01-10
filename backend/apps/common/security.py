"""
安全事件与敏感密钥工具
- 统一记录登录/验证码等敏感操作的安全日志，便于审计
- 提供动态 Flag HMAC 密钥的统一读取与加固提醒
"""

from __future__ import annotations

from typing import Any, Optional

from django.conf import settings
from django.http import HttpRequest

from apps.common.infra.logger import get_logger, logger_extra
from apps.system.services import ConfigService

security_logger = get_logger("apps.security")
_flag_secret_warned = False


def get_flag_secret() -> str:
    """
    获取动态 Flag 使用的 HMAC 密钥
    - 优先后台 SystemConfig.FLAG_SECRET，其次 settings.FLAG_SECRET
    - 若长度不足 16 会记录一次警告，提示管理员更换高熵密钥
    """
    global _flag_secret_warned

    cfg_service = ConfigService()
    resolved = cfg_service.get("FLAG_SECRET", getattr(settings, "FLAG_SECRET", None))
    resolved = resolved or getattr(settings, "FLAG_SECRET", None)
    if not resolved:
        raise RuntimeError("FLAG_SECRET 未配置，无法生成动态 Flag，请在后台或环境变量中设置")

    resolved_str = str(resolved)
    if len(resolved_str) < 16 and not _flag_secret_warned:
        security_logger.warning(
            "FLAG_SECRET 长度不足 16，建议更新为高熵随机值（32+ 字符）以防止动态 Flag 被伪造"
        )
        _flag_secret_warned = True

    return resolved_str


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
