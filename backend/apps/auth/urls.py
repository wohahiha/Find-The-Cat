# -*- coding: utf-8 -*-
"""
认证与权限路由配置

当前仅注册占位接口，后续可按需挂载到全局 urls。
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PermissionViewSet, RoleViewSet

router = DefaultRouter()
router.register("roles", RoleViewSet, basename="auth-roles")
router.register("permissions", PermissionViewSet, basename="auth-permissions")

urlpatterns = [
    path("", include(router.urls)),
]
