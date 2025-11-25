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
    log_format = "%(asctime)s %(levelname)s %(name)s %(message)s"
    if fmt_choice == "json":
        log_format = '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}'
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
