from __future__ import annotations

from django.contrib import admin

from .models import Submission

# Admin 配置：查看提交记录。


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    """提交记录后台：便于运营查看判题与得分。"""

    # 列表展示提交关联信息与得分，便于筛查
    list_display = ("contest", "challenge", "user", "team", "status", "is_correct", "blood_rank", "awarded_points", "created_at")
    # 可按比赛/题目/状态/正确性过滤
    list_filter = ("contest", "challenge", "status", "is_correct")
    # 支持按用户名、题目 slug、提交内容搜索
    search_fields = ("user__username", "challenge__slug", "flag_submitted")

    # 只读，禁止新增/修改/删除，管理员仅查看提交记录
    readonly_fields = (
        "contest",
        "challenge",
        "user",
        "team",
        "flag_submitted",
        "status",
        "is_correct",
        "message",
        "awarded_points",
        "blood_rank",
        "solve",
        "created_at",
        "judged_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
