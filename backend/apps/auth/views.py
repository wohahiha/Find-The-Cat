# -*- coding: utf-8 -*-
"""
认证与权限接口层

提供 RBAC 管理占位接口，后续可补充角色/权限 CRUD、OAuth2 配置等。
"""

from rest_framework.viewsets import ViewSet

from apps.common.permissions import IsAdmin
from apps.common.response import success


class RoleViewSet(ViewSet):
    """
    角色管理接口（占位）
    - 后续用于角色列表与基本维护
    """

    permission_classes = [IsAdmin]

    def list(self, request):
        """
        获取角色列表（当前返回空列表占位）
        """
        return success({"items": []})


class PermissionViewSet(ViewSet):
    """
    权限管理接口（占位）
    - 后续用于权限定义与分配
    """

    permission_classes = [IsAdmin]

    def list(self, request):
        """
        获取权限列表（当前返回空列表占位）
        """
        return success({"items": []})
