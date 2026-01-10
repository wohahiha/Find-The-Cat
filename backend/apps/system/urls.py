# -*- coding: utf-8 -*-
"""
系统配置模块 API
- 仅暴露安全的只读接口（如品牌配置）
"""

from django.urls import path
from .views import PublicBrandView

urlpatterns: list[path] = [
    path("public/brand/", PublicBrandView.as_view(), name="public-brand"),
]
