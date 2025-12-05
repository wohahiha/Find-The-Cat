"""
通用辅助函数：
- 提供掩码、类型安全转换等纯工具方法，避免重复代码
- 不包含业务逻辑，便于在各模块安全复用
"""

from __future__ import annotations

from typing import Any, Optional


def mask_email(email: str) -> str:
    """对邮箱做简单掩码，保护隐私"""
    if "@" not in email:
        return email
    name, domain = email.split("@", 1)
    if len(name) <= 2:
        masked = name[0] + "*" * (len(name) - 1)
    else:
        masked = name[0] + "*" * (len(name) - 2) + name[-1]
    return f"{masked}@{domain}"


def mask_mobile(mobile: str) -> str:
    """对手机号做中间掩码"""
    if len(mobile) < 7:
        return mobile
    return mobile[:3] + "****" + mobile[-4:]


def safe_int(value: Any, default: int = 0) -> int:
    """安全转换为 int，失败则返回默认值，防止类型错误导致异常"""
    try:
        return int(value)
    except Exception:
        return default


def get_or_default(data: dict, key: str, default: Optional[Any] = None) -> Any:
    """从字典安全获取值，不存在则返回默认值，减少 KeyError"""
    return data.get(key, default)
