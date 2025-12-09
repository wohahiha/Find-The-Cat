"""
Redis 客户端封装：
- 统一读取 settings 中的 Redis 配置，提供基础的 get/set/incr/json 存取等方法
- 不再提供 mock，Redis 不可用时记录警告并允许上层回退到 DB/非缓存逻辑
"""

from __future__ import annotations

import os
import json
from typing import Any, Optional

from django.conf import settings
from apps.common.exceptions import CacheUnavailableError
from apps.common.infra.logger import get_logger

_logger = get_logger(__name__)

try:  # pragma: no cover - 环境缺少 redis 时降级
    import redis  # type: ignore
except Exception:  # pragma: no cover
    redis = None


def _get_client():
    """
    获取 Redis 客户端；不可用时返回 None 并记录警告
    - 适配生产：Redis 未安装/未启动时不抛致命异常，由调用方选择回退方案
    """
    if not redis:
        _logger.warning("未安装 redis 客户端，跳过缓存读写", extra={"service": "redis"})
        return None
    host = getattr(settings, "REDIS_HOST", "127.0.0.1")
    port = int(getattr(settings, "REDIS_PORT", 6379))
    db = int(getattr(settings, "REDIS_DB_CACHE", 0))
    password = os.getenv("REDIS_PASSWORD", None)
    connect_timeout = float(os.getenv("REDIS_CONNECT_TIMEOUT", 0.2))
    socket_timeout = float(os.getenv("REDIS_SOCKET_TIMEOUT", 0.5))
    try:
        return redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=True,
            socket_connect_timeout=connect_timeout,
            socket_timeout=socket_timeout,
        )
    except Exception:
        _logger.warning("Redis 连接失败，已跳过缓存", extra={"host": host, "port": port, "db": db})
        return None


def set(key: str, value: Any, ex: Optional[int] = None) -> None:
    """
    设置键值，可选过期时间（秒）
    """
    client = _get_client()
    if client is None:
        return
    try:
        client.set(key, value, ex=ex)
    except Exception:
        _logger.warning("Redis 写入失败，已跳过", extra={"key": key}, exc_info=True)


def get(key: str) -> Optional[Any]:
    """
    获取键值，若过期或不存在返回 None
    """
    client = _get_client()
    if client is None:
        return None
    try:
        return client.get(key)
    except Exception:
        _logger.warning("Redis 读取失败，已跳过", extra={"key": key}, exc_info=True)
        return None


def incr(key: str, amount: int = 1, ex: Optional[int] = None) -> int:
    """
    自增并可选设置过期时间
    """
    client = _get_client()
    if client is None:
        raise CacheUnavailableError(message="Redis 不可用，无法执行计数器")
    try:
        if ex:
            # pipeline 保证在设置过期前写入
            pipe = client.pipeline()
            pipe.incrby(key, amount)
            pipe.expire(key, ex)
            val, _ = pipe.execute()
            return int(val)
        return int(client.incrby(key, amount))
    except Exception as exc:
        _logger.warning("Redis 自增失败", extra={"key": key})
        raise CacheUnavailableError(message="Redis 不可用，计数器失败") from exc


def delete(key: str) -> None:
    """删除键，失败时跳过"""
    client = _get_client()
    if client is None:
        return
    try:
        client.delete(key)
    except Exception:
        _logger.warning("Redis 删除键失败，已跳过", extra={"key": key})


def acquire_lock(key: str, *, ex: Optional[int] = None) -> bool:
    """
    使用 SET NX 获取分布式锁，失败返回 False
    """
    client = _get_client()
    if client is None:
        return False
    try:
        return bool(client.set(key, "1", nx=True, ex=ex))
    except Exception:
        _logger.warning("Redis 加锁失败，已跳过", extra={"key": key}, exc_info=True)
        return False


def release_lock(key: str) -> None:
    """释放分布式锁，失败时跳过"""
    client = _get_client()
    if client is None:
        return
    try:
        client.delete(key)
    except Exception:
        _logger.warning("Redis 解锁失败，已跳过", extra={"key": key})


def lpush(key: str, *values) -> int:
    """列表左插入"""
    client = _get_client()
    if client is None:
        raise CacheUnavailableError(message="Redis 不可用，列表写入失败")
    try:
        return int(client.lpush(key, *values))
    except Exception as exc:
        _logger.warning("Redis 列表写入失败", extra={"key": key})
        raise CacheUnavailableError(message="Redis 不可用，列表写入失败") from exc


def lrange(key: str, start: int = 0, end: int = -1):
    """列表切片读取"""
    client = _get_client()
    if client is None:
        return []
    try:
        return client.lrange(key, start, end)
    except Exception:
        _logger.warning("Redis 列表读取失败，已跳过", extra={"key": key}, exc_info=True)
        return []


def set_json(key: str, data: Any, ex: Optional[int] = None) -> None:
    """以 JSON 序列化存储数据，方便结构化缓存"""
    set(key, json.dumps(data), ex=ex)


def get_json(key: str) -> Optional[Any]:
    """获取 JSON 数据并反序列化，失败返回 None"""
    raw = get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None
