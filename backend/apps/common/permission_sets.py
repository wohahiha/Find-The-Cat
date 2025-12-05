"""
权限集中心（common.permission_sets）
- 从 apps.auth.rbac 动态构建权限列表
- 提供后端/前端显示用的中文标签
- 默认组权限预制，避免解析或应用复制行为
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

from apps.auth.rbac import (
    DEFAULT_ADMIN_GROUP,
    DEFAULT_ADMIN_GROUP_PERMS,
    DEFAULT_USER_GROUP,
    DEFAULT_USER_GROUP_PERMS,
    PERMISSIONS,
)

PermissionKey = Tuple[str, str]


@dataclass(frozen=True)
class PermissionItem:
    app_label: str
    codename: str
    category: str
    resource: str
    action: str
    admin_only: bool = False
    user_default: bool = False

    @property
    def label(self) -> str:
        return f"{self.category}-{self.resource}-{self.action}"


def _build_items() -> Tuple[PermissionItem, ...]:
    items = []
    for perm in PERMISSIONS:
        app_label, codename = perm.code.split(".", 1)
        items.append(
            PermissionItem(
                app_label=app_label,
                codename=codename,
                category=perm.category,
                resource=perm.resource,
                action=perm.action,
                admin_only=perm.admin_only,
                user_default=perm.user_default,
            )
        )
    return tuple(items)


PERMISSION_ITEMS: Tuple[PermissionItem, ...] = _build_items()
PERMISSION_LABELS: Dict[PermissionKey, str] = {
    (item.app_label, item.codename): item.label for item in PERMISSION_ITEMS
}


def get_permission_label(value: str | PermissionKey) -> str:
    """将 app.codename 或 (app, codename) 转为中文标签，未配配到时不修改原始值"""
    if isinstance(value, tuple):
        app_label, codename = value
    else:
        if "." not in value:
            return value
        app_label, codename = value.split(".", 1)
    return PERMISSION_LABELS.get((app_label, codename), f"{app_label}.{codename}")


DEFAULT_ADMIN_GROUP_NAME = DEFAULT_ADMIN_GROUP
DEFAULT_USER_GROUP_NAME = DEFAULT_USER_GROUP

GROUP_PERMISSION_PRESETS = {
    DEFAULT_ADMIN_GROUP_NAME: tuple(DEFAULT_ADMIN_GROUP_PERMS),
    DEFAULT_USER_GROUP_NAME: tuple(DEFAULT_USER_GROUP_PERMS),
}


def iter_permission_labels(keys: Iterable[str | PermissionKey]) -> List[str]:
    """批量转换中文标签，保持顺序"""
    labels: List[str] = []
    for key in keys:
        labels.append(get_permission_label(key))
    return labels
