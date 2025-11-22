from __future__ import annotations

from django.contrib import admin

from .models import MachineInstance

# Admin 配置：查看靶机实例状态。


@admin.register(MachineInstance)
class MachineInstanceAdmin(admin.ModelAdmin):
    """靶机实例后台：展示容器、端口与状态。"""

    list_display = ("contest", "challenge", "user", "team", "host", "port", "status", "created_at")
    list_filter = ("contest", "challenge", "status")
    search_fields = ("container_id", "challenge__slug", "user__username")
