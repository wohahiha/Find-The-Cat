"""
日志封装：提供统一的日志记录器，符合 FTC 日志规范

- 通过日志路径配置文件输出
- 支持 JSON 和 PLAIN 两种格式
- 自动轮转日志文件（按日期）
- 自动注入请求上下文（request_id、user_id、account_id、username、ip 等）

参考文档：docs/日志规范.md
"""

from __future__ import annotations

import logging
import logging.handlers
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from django.conf import settings as django_settings

# 延迟导入，避免循环依赖
_configured = False


class FTCJSONFormatter(logging.Formatter):
    """
    FTC JSON格式化器：符合日志标准的JSON格式

    输出示例：
    {"timestamp": "2025-11-28 16:57:25", "level": "INFO", "logger": "apps.accounts.services",
     "message": "用户登录成功", "username": "admin", "account_id": 1, "ip_address": "127.0.0.1"}
    """

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录为JSON格式"""
        import json
        from apps.common.utils.request_context import get_request_context

        # 获取请求上下文
        ctx = get_request_context()

        # 构建日志字典
        log_dict = {
            "timestamp": datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # 添加可选的上下文字段（仅在有值时添加）
        if ctx.get("username"):
            log_dict["username"] = ctx["username"]
        if ctx.get("user_id") is not None:
            log_dict["user_id"] = ctx["user_id"]
        if ctx.get("account_id") is not None:
            log_dict["account_id"] = ctx["account_id"]
        if ctx.get("ip"):
            log_dict["ip_address"] = ctx["ip"]
        if ctx.get("path"):
            log_dict["request_path"] = ctx["path"]
        if ctx.get("request_id"):
            log_dict["request_id"] = ctx["request_id"]

        # 添加异常信息（如果有）
        if record.exc_info:
            log_dict["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_dict, ensure_ascii=False)


class FTCPlainFormatter(logging.Formatter):
    """
    FTC PLAIN格式化器：符合日志标准的纯文本格式

    格式：{timestamp} {level} {logger} {message} [{username}|{account_id}|{ip_address}|{request_path}]

    输出示例：
    2025-11-28 16:57:25 INFO apps.accounts.services 用户登录成功 [admin|1|127.0.0.1|/api/accounts/auth/login/]
    """

    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录为PLAIN格式"""
        from apps.common.utils.request_context import get_request_context

        # 获取请求上下文
        ctx = get_request_context()

        # 格式化时间戳
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")

        # 获取基本字段
        level = record.levelname
        logger_name = record.name
        message = record.getMessage()

        # 构建上下文部分 [username|account_id|ip|path]
        username = ctx.get("username") or "-"
        account_id = str(ctx.get("account_id")) if ctx.get("account_id") is not None else "-"
        ip_address = ctx.get("ip") or "-"
        request_path = ctx.get("path") or "-"

        context_info = f"[{username}|{account_id}|{ip_address}|{request_path}]"

        # 组合完整日志
        log_line = f"{timestamp} {level} {logger_name} {message} {context_info}"

        # 添加异常信息（如果有）
        if record.exc_info:
            log_line += "\n" + self.formatException(record.exc_info)

        return log_line


def _resolve_log_file_path(log_dir: str) -> str:
    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(parents=True, exist_ok=True)
    return str(log_dir_path / "system.log")


def get_log_path_from_config() -> str:
    """
    从系统配置读取LOG_PATH并构建完整的日志文件路径

    返回：{LOG_PATH}/system.log 的绝对路径
    默认值：logs/system.log
    """
    try:
        from django.apps import apps as django_apps
        if not django_apps.apps_ready:
            return get_log_path_from_settings()
        from apps.system.models import SystemConfig

        config = SystemConfig.objects.filter(key="LOG_PATH").first()
        log_dir = config.value if config else getattr(django_settings, "LOG_PATH", "logs")
    except Exception:
        # 如果数据库未初始化，使用默认值
        log_dir = getattr(django_settings, "LOG_PATH", "logs")

    return _resolve_log_file_path(log_dir)


def get_log_path_from_settings() -> str:
    """基于 settings.LOG_PATH 生成日志文件路径"""
    log_dir = getattr(django_settings, "LOG_PATH", "logs")
    return _resolve_log_file_path(log_dir)


def configure_logging(force: bool = False, *, level: Optional[int] = None, log_file_path: Optional[str] = None) -> None:
    """
    配置FTC日志系统

    配置内容：
    - 使用PLAIN格式（人类可读，易于grep）
    - 按日期自动轮转（每天午夜）
    - 保留30天历史日志
    - 自动注入请求上下文

    参数：
        force: 是否强制重新配置（默认只配置一次）
    """
    global _configured
    if _configured and not force:
        return

    # 获取配置
    log_level = level if level is not None else logging.INFO
    log_file_path = log_file_path if log_file_path is not None else get_log_path_from_config()

    # 创建根logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # 清除已有的handlers（避免重复配置，同时关闭旧文件避免资源告警）
    for handler in list(root_logger.handlers):
        try:
            handler.close()
        except Exception:
            pass
    root_logger.handlers.clear()

    # 创建按日期轮转的文件handler
    # when='midnight': 每天午夜轮转
    # interval=1: 每1天
    # backupCount=30: 保留30天历史
    # encoding='utf-8': 支持中文
    class SafeTimedRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
        """
        自定义日志 Handler：在 Windows 上轮转失败时跳过或重试，避免 PermissionError 中断日志
        """

        def doRollover(self):
            try:
                super().doRollover()
            except PermissionError:
                # Windows 文件被占用时跳过一次轮转，下次写入再尝试
                pass

    file_handler = SafeTimedRotatingFileHandler(
        filename=log_file_path,
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8',
        delay=True,  # 延迟打开文件，避免多进程抢占导致轮转失败
    )
    file_handler.suffix = "%Y-%m-%d"  # 轮转文件后缀：system.log.2025-11-28
    file_handler.setLevel(log_level)

    def _force_rollover_if_outdated(handler: logging.handlers.TimedRotatingFileHandler) -> None:
        """
        若现有日志文件的日期早于今天（例如午夜停机导致错过轮转），或文件过大，尝试补一次轮转。
        """
        try:
            if not os.path.exists(handler.baseFilename):
                return

            last_write = datetime.fromtimestamp(os.path.getmtime(handler.baseFilename)).date()
            today = datetime.now().date()
            size_bytes = os.path.getsize(handler.baseFilename)
            rollover_mb = int(os.getenv("LOG_FORCE_ROLLOVER_MB", "50"))

            if last_write < today or size_bytes > rollover_mb * 1024 * 1024:
                handler.doRollover()
        except Exception:
            # 兼容 Windows 文件占用或并发写入，失败时跳过，下一次写入再尝试
            pass

    _force_rollover_if_outdated(file_handler)

    # 使用PLAIN格式化器（默认）
    formatter = FTCPlainFormatter()
    file_handler.setFormatter(formatter)

    # 添加handler到根logger
    root_logger.addHandler(file_handler)

    # 可选：添加控制台输出（开发环境用）
    if os.getenv("DEBUG", "False").lower() == "true":
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    _configured = True


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    获取logger实例

    使用方式：
        logger = get_logger(__name__)
        logger.info("用户登录成功")
        logger.warning("验证码已过期")
        logger.error("数据库连接失败", exc_info=True)

    参数：
        name: logger名称，推荐使用__name__（自动获取模块路径）

    返回：
        配置好的logger实例
    """
    # 确保日志系统已配置
    if not _configured:
        configure_logging()

    return logging.getLogger(name)


# 保留向后兼容的工具函数
SENSITIVE_KEYS = {"password", "token", "flag", "code", "email_code", "auth_code", "captcha", "captcha_code"}


def sanitize_extra(extra: Optional[dict] = None) -> dict:
    """
    过滤敏感字段，避免在日志中泄露密码/验证码/Flag等

    敏感字段列表：password、token、flag、code、email_code、auth_code、captcha等
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
    """封装extra，自动过滤敏感字段"""
    return sanitize_extra(extra)


def merge_extra(base: Optional[dict], extra: Optional[dict]) -> dict:
    """合并多个extra字典并过滤敏感字段"""
    merged = {}
    if base:
        merged.update(base)
    if extra:
        merged.update(extra)
    return logger_extra(merged)
