# -*- coding: utf-8 -*-
"""
认证与权限接口层

提供 RBAC 管理占位接口，后续可补充角色/权限 CRUD、OAuth2 配置等。
"""

from rest_framework import serializers
from rest_framework.viewsets import ViewSet
from drf_spectacular.utils import extend_schema

from apps.common.permissions import IsAdmin
from apps.common.response import success


class RoleViewSet(ViewSet):
    """
    角色管理接口（占位）
    - 后续用于角色列表与基本维护
    """

    permission_classes = [IsAdmin]

    @extend_schema(summary="获取角色列表（占位）", description="获取角色列表（当前返回空列表占位）")
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

    @extend_schema(summary="获取权限列表（占位）", description="获取权限列表（当前返回空列表占位）")
    def list(self, request):
        """
        获取权限列表（当前返回空列表占位）
        """
        return success({"items": []})


# 占位 Serializer，供 drf-spectacular 识别
class EmptySerializer(serializers.Serializer):
    pass


RoleViewSet.serializer_class = EmptySerializer
PermissionViewSet.serializer_class = EmptySerializer
