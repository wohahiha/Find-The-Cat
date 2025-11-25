"""
Redis 客户端封装：
- 统一读取 settings 中的 Redis 配置，提供基础的 get/set/incr/json 存取等方法。
- 预留 mock 模式（无 Redis 时使用内存字典），便于本地开发/测试。
"""

from __future__ import annotations

import os
import json
import time
from typing import Any, Optional

import django
from django.conf import settings
from apps.common.infra.logger import get_logger

_USE_MOCK = os.getenv("REDIS_USE_MOCK", "0") == "1"
_mock_store: dict[str, Any] = {}
_logger = get_logger(__name__)

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover
    redis = None
    _USE_MOCK = True


def _get_client():
    """获取 Redis 客户端，mock 模式返回 None，缺少依赖时报错。"""
    if _USE_MOCK:
        return None
    if not redis:
        raise RuntimeError("未安装 redis 客户端，请 pip install redis 或开启 REDIS_USE_MOCK=1")
    host = getattr(settings, "REDIS_HOST", "127.0.0.1")
    port = int(getattr(settings, "REDIS_PORT", 6379))
    db = int(getattr(settings, "REDIS_DB_CACHE", 0))
    password = os.getenv("REDIS_PASSWORD", None)
    try:
        return redis.Redis(host=host, port=port, db=db, password=password, decode_responses=True)
    except Exception as exc:
        _logger.exception(
            "Redis 连接失败",
            extra={"host": host, "port": port, "db": db},
        )
        raise


def set(key: str, value: Any, ex: Optional[int] = None) -> None:
    """
    设置键值，可选过期时间（秒）。
    - mock 模式：写入内存并按过期时间清理。
    """
    if _USE_MOCK:
        _mock_store[key] = (value, time.time() + ex if ex else None)
        return
    client = _get_client()
    client.set(key, value, ex=ex)


def get(key: str) -> Optional[Any]:
    """
    获取键值，若过期或不存在返回 None。
    - mock 模式：自动清理过期键。
    """
    if _USE_MOCK:
        item = _mock_store.get(key)
        if not item:
            return None
        value, expire_at = item
        if expire_at and expire_at < time.time():
            _mock_store.pop(key, None)
            return None
        return value
    client = _get_client()
    return client.get(key)


def incr(key: str, amount: int = 1, ex: Optional[int] = None) -> int:
    """
    自增并可选设置过期时间。
    - mock 模式：基于内存自增。
    """
    if _USE_MOCK:
        current = int(get(key) or 0) + amount
        set(key, current, ex=ex)
        return current
    client = _get_client()
    if ex:
        # pipeline 保证在设置过期前写入
        pipe = client.pipeline()
        pipe.incrby(key, amount)
        pipe.expire(key, ex)
        val, _ = pipe.execute()
        return int(val)
    return int(client.incrby(key, amount))


def delete(key: str) -> None:
    """删除键（mock 模式删除内存记录）。"""
    if _USE_MOCK:
        _mock_store.pop(key, None)
        return
    client = _get_client()
    client.delete(key)


def lpush(key: str, *values) -> int:
    """列表左插入（mock 模式使用内存 list）。"""
    if _USE_MOCK:
        lst = _mock_store.setdefault(key, [])
        lst[0:0] = list(values)
        return len(lst)
    client = _get_client()
    return int(client.lpush(key, *values))


def lrange(key: str, start: int = 0, end: int = -1):
    """列表切片读取（mock 模式从内存 list 返回）。"""
    if _USE_MOCK:
        lst = _mock_store.get(key, [])
        return lst[start : end + 1 if end != -1 else None]
    client = _get_client()
    return client.lrange(key, start, end)


def set_json(key: str, data: Any, ex: Optional[int] = None) -> None:
    """以 JSON 序列化存储数据，方便结构化缓存。"""
    set(key, json.dumps(data), ex=ex)


def get_json(key: str) -> Optional[Any]:
    """获取 JSON 数据并反序列化，失败返回 None。"""
    raw = get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None
