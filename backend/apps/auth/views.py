# -*- coding: utf-8 -*-
"""
认证与权限接口层

提供 RBAC 管理占位接口，后续可补充角色/权限 CRUD、OAuth2 配置等。
"""

from django.contrib.auth.models import Group
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.common.permissions import IsAdmin
from apps.common import response
from apps.common.exceptions import NotFoundError
from apps.auth.services import RBACService
from apps.auth.rbac import PERMISSIONS


class PermissionSerializer(serializers.Serializer):
    code = serializers.CharField()
    category = serializers.CharField()
    resource = serializers.CharField()
    action = serializers.CharField()
    admin_only = serializers.BooleanField()
    user_default = serializers.BooleanField()


class PermissionViewSet(ViewSet):
    """
    权限字典：仅管理员可读
    """

    permission_classes = [IsAdmin]
    serializer_class = PermissionSerializer

    @extend_schema(summary="权限字典", responses=PermissionSerializer(many=True))
    def list(self, request):
        RBACService.sync_permissions_and_defaults()
        items = RBACService.list_permissions()
        return response.success({"items": items})


class RoleSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField()
    is_builtin = serializers.BooleanField(read_only=True)
    permissions = serializers.ListField(child=serializers.CharField(), allow_empty=True)


class RoleViewSet(ViewSet):
    """
    角色管理：基于 Django Group
    """

    permission_classes = [IsAdmin]
    serializer_class = RoleSerializer
    # 显式声明路径参数类型，便于 OpenAPI 生成
    lookup_url_kwarg = "id"
    lookup_value_regex = r"\d+"

    role_id_param = OpenApiParameter(
        name="id",
        type=int,
        location=OpenApiParameter.PATH,
        description="角色 ID",
    )

    @extend_schema(summary="角色列表", responses=RoleSerializer(many=True))
    def list(self, request):
        RBACService.sync_permissions_and_defaults()
        groups = Group.objects.all().order_by("name")
        items = [RBACService.role_payload(g) for g in groups]
        return response.success({"items": items})

    @extend_schema(summary="创建角色", request=RoleSerializer, responses=RoleSerializer)
    def create(self, request):
        serializer = RoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        group = RBACService.create_role(data["name"], data.get("permissions") or [])
        return response.created({"role": RBACService.role_payload(group)}, message="角色已创建")

    @extend_schema(summary="角色详情", responses=RoleSerializer, parameters=[role_id_param])
    def retrieve(self, request, pk=None):
        RBACService.sync_permissions_and_defaults()
        group = Group.objects.filter(pk=pk).first()
        if not group:
            raise NotFoundError(message="角色不存在")
        return response.success({"role": RBACService.role_payload(group)})

    @extend_schema(summary="更新角色", request=RoleSerializer, responses=RoleSerializer, parameters=[role_id_param])
    def update(self, request, pk=None):
        RBACService.sync_permissions_and_defaults()
        group = Group.objects.filter(pk=pk).first()
        if not group:
            raise NotFoundError(message="角色不存在")
        serializer = RoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        group = RBACService.update_role(group, name=data.get("name"), permissions=data.get("permissions"))
        return response.success({"role": RBACService.role_payload(group)}, message="角色已更新")

    @extend_schema(summary="部分更新角色", request=RoleSerializer, responses=RoleSerializer, parameters=[role_id_param])
    def partial_update(self, request, pk=None):
        RBACService.sync_permissions_and_defaults()
        group = Group.objects.filter(pk=pk).first()
        if not group:
            raise NotFoundError(message="角色不存在")
        serializer = RoleSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        group = RBACService.update_role(group, name=data.get("name"), permissions=data.get("permissions"))
        return response.success({"role": RBACService.role_payload(group)}, message="角色已更新")

    @extend_schema(summary="删除角色", parameters=[role_id_param])
    def destroy(self, request, pk=None):
        RBACService.sync_permissions_and_defaults()
        group = Group.objects.filter(pk=pk).first()
        if not group:
            raise NotFoundError(message="角色不存在")
        RBACService.delete_role(group)
        return Response(status=status.HTTP_204_NO_CONTENT)
