from __future__ import annotations

from django.contrib import admin

from .models import Submission

# Admin 配置：查看提交记录。


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    """提交记录后台：便于运营查看判题与得分。"""

    list_display = ("contest", "challenge", "user", "team", "status", "is_correct", "awarded_points", "created_at")
    list_filter = ("contest", "challenge", "status", "is_correct")
    search_fields = ("user__username", "challenge__slug", "flag_submitted")
