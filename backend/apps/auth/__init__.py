"""
权限中心（apps.auth）
- 权限定义与包含规则
- 内置组/角色配置及同步工具
"""

from __future__ import annotations

from .rbac import (
    PermissionDef,
    PERMISSIONS,
    DEFAULT_ADMIN_GROUP,
    DEFAULT_USER_GROUP,
    DEFAULT_ADMIN_GROUP_PERMS,
    DEFAULT_USER_GROUP_PERMS,
    IMPLIED_PERMISSIONS,
    expand_with_implied,
)
# 注意：避免在此处导入涉及 Django ORM 的模块（如 group.py），
# 以防止 Django 应用尚未就绪时触发 AppRegistryNotReady。

__all__ = [
    "PermissionDef",
    "PERMISSIONS",
    "DEFAULT_ADMIN_GROUP",
    "DEFAULT_USER_GROUP",
    "DEFAULT_ADMIN_GROUP_PERMS",
    "DEFAULT_USER_GROUP_PERMS",
    "IMPLIED_PERMISSIONS",
    "expand_with_implied",
]
