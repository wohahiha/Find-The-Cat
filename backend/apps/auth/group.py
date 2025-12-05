"""
权限组工具（apps.auth.group）
- 声明内置角色/组与权限集
- 提供后端同步 Django Group/Permission 的工具方法
"""

from __future__ import annotations

from typing import Dict, Set

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from .rbac import (
    DEFAULT_ADMIN_GROUP,
    DEFAULT_ADMIN_GROUP_PERMS,
    DEFAULT_USER_GROUP,
    DEFAULT_USER_GROUP_PERMS,
    PERMISSIONS,
)


def list_builtin_groups() -> Dict[str, Set[str]]:
    """返回内置组与权限 code 集合"""
    return {
        DEFAULT_ADMIN_GROUP: set(DEFAULT_ADMIN_GROUP_PERMS),
        DEFAULT_USER_GROUP: set(DEFAULT_USER_GROUP_PERMS),
    }


def ensure_permission_objects() -> None:
    """确保自定义权限存在于 auth_permission 中：
    - 使用 bizperm 作为空模型，app_label 保持原模块
    - 无需为每个权限单独建表"""
    for perm in PERMISSIONS:
        app_label, codename = perm.code.split(".", 1)
        ct, _ = ContentType.objects.get_or_create(app_label=app_label, model="bizperm")
        Permission.objects.get_or_create(
            codename=codename,
            content_type=ct,
            defaults={"name": f"{perm.category}-{perm.resource}-{perm.action}"},
        )


def _fetch_permission(app_label: str, codename: str) -> Permission:
    """助手函数：获取指定权限，如果不存在则会使用占位 ContentType 创建"""
    ct, _ = ContentType.objects.get_or_create(app_label=app_label, model="bizperm")
    perm, _ = Permission.objects.get_or_create(
        codename=codename,
        content_type=ct,
        defaults={"name": f"{app_label}.{codename}"},
    )
    return perm


def sync_builtin_groups() -> None:
    """建立/更新默认组，绑定须要的权限"""
    ensure_permission_objects()
    groups = list_builtin_groups()
    for name, codes in groups.items():
        group, _ = Group.objects.get_or_create(name=name)
        perms = []
        for code in codes:
            app_label, codename = code.split(".", 1)
            perms.append(_fetch_permission(app_label, codename))
        group.permissions.set(perms)


def assign_default_group(user, is_admin: bool = False) -> None:
    """为新用户加入默认组： is_admin=True 表示管理组入口"""
    # 确保内置组与权限已同步，避免缺失导致无权限
    sync_builtin_groups()
    target = DEFAULT_ADMIN_GROUP if is_admin else DEFAULT_USER_GROUP
    group, _ = Group.objects.get_or_create(name=target)
    user.groups.add(group)
