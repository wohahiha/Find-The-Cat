# -*- coding: utf-8 -*-
"""
认证与权限业务逻辑层

后续将承载：
- 角色/权限的增删改查
- 轻量级 RBAC 判定
- OAuth2 / 单点登录等认证扩展
"""

from __future__ import annotations

from typing import Iterable, List, Dict, Any

from django.contrib.auth.models import Group, Permission
from django.db import transaction

from apps.common.base.base_service import BaseService
from apps.common.exceptions import ValidationError, ConflictError
from apps.auth.group import ensure_permission_objects, sync_builtin_groups, list_builtin_groups
from apps.auth.rbac import PERMISSIONS, DEFAULT_ADMIN_GROUP, DEFAULT_USER_GROUP


def _permission_map() -> Dict[str, Permission]:
    """返回 code -> Permission 对象映射，确保不存在空洞"""
    ensure_permission_objects()
    perms = Permission.objects.filter(
        codename__in=[p.code.split(".", 1)[1] for p in PERMISSIONS],
        content_type__app_label__in={p.code.split(".", 1)[0] for p in PERMISSIONS},
    )
    return {f"{p.content_type.app_label}.{p.codename}": p for p in perms}


def permission_dict() -> List[dict]:
    """权限字典：提供中文分类/资源/动作，方便前端展示"""
    return [
        {
            "code": p.code,
            "category": p.category,
            "resource": p.resource,
            "action": p.action,
            "admin_only": p.admin_only,
            "user_default": p.user_default,
        }
        for p in PERMISSIONS
    ]


def is_builtin_role(name: str) -> bool:
    """判断是否内置角色"""
    return name in {DEFAULT_ADMIN_GROUP, DEFAULT_USER_GROUP}


class RBACService(BaseService):
    """
    RBAC 业务服务：同步权限、管理角色
    """

    atomic_enabled = True

    def perform(self, *args, **kwargs):
        return None

    @staticmethod
    def sync_permissions_and_defaults() -> None:
        """同步权限字典和默认角色"""
        ensure_permission_objects()
        sync_builtin_groups()

    @staticmethod
    def list_permissions() -> List[dict]:
        """权限字典（含中文分类/资源/动作）"""
        RBACService.sync_permissions_and_defaults()
        return permission_dict()

    @staticmethod
    def role_payload(group: Group) -> dict:
        """序列化角色"""
        codes = [f"{p.content_type.app_label}.{p.codename}" for p in group.permissions.all()]
        return {
            "id": group.id,
            "name": group.name,
            "is_builtin": is_builtin_role(group.name),
            "permissions": codes,
        }

    @staticmethod
    def _resolve_permissions(codes: Iterable[str]) -> List[Permission]:
        """将 code 转为 Permission 对象并校验合法性"""
        code_set = {c for c in codes if c}
        if not code_set:
            return []
        valid_codes = {p.code for p in PERMISSIONS}
        invalid = code_set - valid_codes
        if invalid:
            raise ValidationError(message=f"未知的权限码: {', '.join(sorted(invalid))}")
        perm_map = _permission_map()
        perms: List[Permission] = []
        missing = []
        for code in code_set:
            perm = perm_map.get(code)
            if not perm:
                missing.append(code)
            else:
                perms.append(perm)
        if missing:
            raise ValidationError(message=f"缺少权限对象: {', '.join(missing)}，请先同步权限")
        return perms

    @staticmethod
    @transaction.atomic
    def create_role(name: str, permissions: Iterable[str]) -> Group:
        RBACService.sync_permissions_and_defaults()
        name = (name or "").strip()
        if not name:
            raise ValidationError(message="角色名称不能为空")
        if Group.objects.filter(name=name).exists():
            raise ConflictError(message="角色名称已存在")
        perms = RBACService._resolve_permissions(permissions)
        group = Group.objects.create(name=name)
        if perms:
            group.permissions.set(perms)
        return group

    @staticmethod
    @transaction.atomic
    def update_role(group: Group, *, name: str | None = None, permissions: Iterable[str] | None = None) -> Group:
        if is_builtin_role(group.name):
            # 内置角色不允许改名，但允许调整权限（如确有需要）
            if name and name != group.name:
                raise ConflictError(message="内置角色不允许修改名称")
        if name:
            new_name = name.strip()
            if not new_name:
                raise ValidationError(message="角色名称不能为空")
            if new_name != group.name and Group.objects.filter(name=new_name).exists():
                raise ConflictError(message="角色名称已存在")
            group.name = new_name
        if permissions is not None:
            perms = RBACService._resolve_permissions(permissions)
            group.permissions.set(perms)
        group.save()
        return group

    @staticmethod
    @transaction.atomic
    def delete_role(group: Group) -> None:
        if is_builtin_role(group.name):
            raise ConflictError(message="内置角色不允许删除")
        group.delete()
