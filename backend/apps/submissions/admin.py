from __future__ import annotations

from django.contrib import admin

from .models import Submission


# Admin 配置：查看提交记录


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    """提交记录后台：便于运营查看判题与得分"""

    # 列表展示提交关联信息与得分，便于筛查
    list_display = ("contest", "challenge", "user", "team", "status", "is_correct", "blood_rank", "awarded_points",
                    "bonus_points", "created_at")
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
        "bonus_points",
        "blood_rank",
        "solve",
        "created_at",
        "judged_at",
    )

    def get_form(self, request, obj=None, **kwargs):
        """为提交详情页字段添加简明说明，便于审计"""
        form = super().get_form(request, obj, **kwargs)
        help_texts = {
            "contest": "提交所属比赛，保持与题目一致",
            "challenge": "提交对应的题目，判题依赖此字段",
            "user": "提交人账号，便于追踪行为",
            "team": "提交人所在队伍，个人赛可为空",
            "flag_submitted": "用户提交的原始 Flag 内容",
            "status": "判题状态：正确/错误/重复",
            "is_correct": "判题是否正确的布尔标志",
            "message": "判题提示信息，展示给运营或前台",
            "awarded_points": "本次提交获得的分值，仅正确时有值",
            "bonus_points": "符合 n 血加分规则时的额外得分",
            "blood_rank": "解题血次序，0 表示非正确提交",
            "solve": "关联的解题记录，错误/重复为空",
            "created_at": "提交时间戳，记录选手提交时刻",
            "judged_at": "判题时间戳，便于分析判题延迟",
        }
        for field_name, text in help_texts.items():
            if field_name in form.base_fields:
                form.base_fields[field_name].help_text = text
        return form

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_model_perms(self, request):
        """隐藏独立提交板块，改为在比赛下查看提交记录"""
        return {}
