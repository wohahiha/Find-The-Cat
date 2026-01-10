"""
账户权限相关的工具方法

- ensure_builtin_groups：确保内置的普通用户/管理员分组存在并填充预设权限
- assign_default_admin_permissions / assign_default_user_permissions：为用户分配默认分组与权限
"""

from __future__ import annotations

from django.contrib.auth.models import Group, Permission

from apps.common.permission_sets import (
    DEFAULT_ADMIN_GROUP,
    DEFAULT_USER_GROUP,
    GROUP_PERMISSION_PRESETS,
)
from apps.auth.group import ensure_permission_objects


def _ensure_group(name: str) -> Group:
    """
    确保指定名称的分组存在并填充预设权限：
    - name: 分组名称（普通用户/管理员）
    - 读取 GROUP_PERMISSION_PRESETS，将权限对象绑定到分组
    - 业务场景：初始化默认权限组，供新用户/管理员自动加入，避免权限缺失
    """
    # 获取或创建分组，避免多次调用重复创建
    group, _ = Group.objects.get_or_create(name=name)
    # 获取当前分组预设的权限键列表
    perm_keys = GROUP_PERMISSION_PRESETS.get(name, ())
    if perm_keys:
        perms = []
        # 遍历预设权限键，按 content_type 与 codename 获取 Permission
        for key in perm_keys:
            # 兼容 "app.codename" 字符串或 (app, codename) 元组两种形式
            if isinstance(key, str) and "." in key:
                app_label, codename = key.split(".", 1)
            elif isinstance(key, (tuple, list)) and len(key) == 2:
                app_label, codename = key
            else:
                continue
            perm = Permission.objects.filter(
                content_type__app_label=app_label,
                codename=codename,
            ).first()
            if perm:
                perms.append(perm)
        # 若获取到权限对象，则一次性设置到分组，避免累积旧权限
        if perms:
            group.permissions.set(perms)
    return group


def ensure_builtin_groups() -> None:
    """确保内置的普通用户/管理员分组存在并补齐权限，防止后台/注册流程出现缺少分组的异常"""
    # 先确保权限对象存在（使用占位 ContentType），防止预设权限缺失
    ensure_permission_objects()
    _ensure_group(DEFAULT_USER_GROUP)
    _ensure_group(DEFAULT_ADMIN_GROUP)


def assign_default_admin_permissions(user) -> None:
    """
    为管理员用户分配默认管理员分组：
    - 入参 user：目标用户实例
    - 若未包含管理员组，则创建/获取后添加到用户
    - 业务场景：创建管理员或升级权限时自动补齐默认管理员权限集
    """
    ensure_builtin_groups()
    if not user.groups.filter(name=DEFAULT_ADMIN_GROUP).exists():
        group = _ensure_group(DEFAULT_ADMIN_GROUP)
        user.groups.add(group)


def assign_default_user_permissions(user) -> None:
    """
    为普通用户分配默认用户分组：
    - 入参 user：目标用户实例
    - 若未包含普通用户组，则创建/获取后添加到用户
    - 业务场景：注册/后台创建普通用户时自动赋予基础权限，保证最小可用
    """
    ensure_builtin_groups()
    if not user.groups.filter(name=DEFAULT_USER_GROUP).exists():
        group = _ensure_group(DEFAULT_USER_GROUP)
        user.groups.add(group)
