"""
日志封装：提供统一获取 logger 的入口，便于集中配置格式/输出。

- configure_logging：按环境变量设置日志级别/格式/输出文件。
- get_logger(name)：返回 Python logging 的 logger，默认延用 Django 配置。
"""

from __future__ import annotations

import logging
import os
from typing import Optional


def configure_logging() -> None:
    """
    初始化日志配置。

    - LOG_LEVEL：日志级别（默认为 INFO）
    - LOG_FORMAT：可选 plain/json，json 仅输出 message 与 level
    - LOG_FILE：若设置则输出到文件，否则 stdout
    """
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    fmt_choice = os.getenv("LOG_FORMAT", "plain").lower()
    log_format = "%(asctime)s %(levelname)s %(name)s %(message)s [request_id=%(request_id)s user_id=%(user_id)s ip=%(ip)s path=%(path)s method=%(method)s ua=%(user_agent)s]"
    if fmt_choice == "json":
        log_format = (
            '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s",'
            '"message":"%(message)s","request_id":"%(request_id)s","user_id":"%(user_id)s",'
            '"ip":"%(ip)s","path":"%(path)s","method":"%(method)s","user_agent":"%(user_agent)s"}'
        )
    handlers = None
    log_file = os.getenv("LOG_FILE")
    if log_file:
        handlers = [logging.FileHandler(log_file, encoding="utf-8")]
    logging.basicConfig(level=level, format=log_format, handlers=handlers)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    获取 logger：默认使用模块名或传入的 name。
    """
    return logging.getLogger(name)


SENSITIVE_KEYS = {"password", "token", "flag", "code", "email_code", "auth_code", "captcha", "captcha_code"}


def sanitize_extra(extra: Optional[dict] = None) -> dict:
    """
    过滤敏感字段，避免在日志中泄露密码/验证码/Flag 等。
    """
    if not extra:
        return {}
    sanitized = {}
    for k, v in extra.items():
        if k.lower() in SENSITIVE_KEYS:
            sanitized[k] = "***"
        else:
            sanitized[k] = v
    return sanitized


def logger_extra(extra: Optional[dict] = None) -> dict:
    """封装 extra，自动过滤敏感字段。"""
    return sanitize_extra(extra)


def merge_extra(base: Optional[dict], extra: Optional[dict]) -> dict:
    merged = {}
    if base:
        merged.update(base)
    if extra:
        merged.update(extra)
    return logger_extra(merged)


class RequestContextFilter(logging.Filter):
    """将 request_context 注入日志 record，确保 formatter 有字段可用。"""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            from apps.common.utils.request_context import get_request_context
        except Exception:
            return True
        ctx = get_request_context()
        for k, v in ctx.items():
            setattr(record, k, v if v is not None else "")
        if not hasattr(record, "user_agent"):
            setattr(record, "user_agent", "")
        return True
