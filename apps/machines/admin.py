from __future__ import annotations

from django.contrib import admin

from .models import MachineInstance


# Admin 配置：查看靶机实例状态


@admin.register(MachineInstance)
class MachineInstanceAdmin(admin.ModelAdmin):
    """靶机实例后台：展示容器、端口与状态"""

    # 列表展示关键字段，便于排查端口/容器状态
    list_display = ("contest", "challenge", "user", "team", "host", "port", "status", "created_at")
    # 支持按比赛/题目/状态过滤
    list_filter = ("contest", "challenge", "status")
    # 支持根据容器 ID、题目 slug、用户名搜索
    search_fields = ("container_id", "challenge__slug", "user__username")

    def get_form(self, request, obj=None, **kwargs):
        """为靶机实例详情页字段添加简明说明，便于排查"""
        form = super().get_form(request, obj, **kwargs)
        help_texts = {
            "contest": "实例所属比赛，用于权限与榜单范围关联",
            "challenge": "实例关联题目，决定容器镜像与 Flag 生成逻辑",
            "user": "启动该实例的用户，便于审计溯源",
            "team": "所属队伍（个人赛为空），用于队伍级限流与权限",
            "container_id": "Docker 容器 ID，空表示尚未分配或已清理",
            "host": "实例所在主机地址，通常为容器宿主机",
            "port": "映射到宿主机的端口，供选手访问",
            "status": "当前实例状态：运行中/已停止/异常",
        }
        for name, text in help_texts.items():
            if name in form.base_fields:
                form.base_fields[name].help_text = text
        return form

    def get_model_perms(self, request):
        """隐藏独立靶机实例板块，改为在题目下查看"""
        return {}
