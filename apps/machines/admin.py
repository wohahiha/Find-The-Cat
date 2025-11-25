from __future__ import annotations

from django.contrib import admin

from .models import MachineInstance

# Admin 配置：查看靶机实例状态。


@admin.register(MachineInstance)
class MachineInstanceAdmin(admin.ModelAdmin):
    """靶机实例后台：展示容器、端口与状态。"""

    # 列表展示关键字段，便于排查端口/容器状态
    list_display = ("contest", "challenge", "user", "team", "host", "port", "status", "created_at")
    # 支持按比赛/题目/状态过滤
    list_filter = ("contest", "challenge", "status")
    # 支持根据容器 ID、题目 slug、用户名搜索
    search_fields = ("container_id", "challenge__slug", "user__username")
