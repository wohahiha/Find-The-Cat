"""
时间工具：提供常用的时间戳与格式化助手，统一使用感知时区的时间
"""

from __future__ import annotations

import datetime
from typing import Union


def now() -> datetime.datetime:
    """返回当前 UTC 时间（感知时区），用于时间敏感的业务"""
    return datetime.datetime.now(datetime.timezone.utc)


def to_timestamp(dt: datetime.datetime) -> int:
    """将 datetime 转为秒级时间戳，缺省时区则补齐 UTC"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return int(dt.timestamp())


def from_timestamp(ts: Union[int, float]) -> datetime.datetime:
    """从时间戳创建 datetime（UTC），用于反序列化时间字段"""
    return datetime.datetime.fromtimestamp(float(ts), tz=datetime.timezone.utc)
