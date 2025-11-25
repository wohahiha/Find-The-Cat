"""
挑战模块后台配置：
- 提供题目/分类/解题记录的管理界面，支持附件上传、字段提示与只读控制。
- 主要服务于运维/出题人后台操作，不参与前台业务逻辑。
"""

from __future__ import annotations

from django.contrib import admin, messages
from django import forms
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from .models import ChallengeCategory, Challenge, ChallengeSolve, ChallengeAttachment
from .services import AttachmentUploadService
from .schemas import AttachmentUploadSchema
from .repo import ChallengeAttachmentRepo


class ChallengeAdminForm(forms.ModelForm):
    """题目后台表单：追加附件上传按钮。"""

    upload_file = forms.FileField(
        required=False,
        label="上传附件",
        help_text="选择本地文件，保存后自动上传并创建附件记录。",
    )
    title = forms.CharField(
        label="题目标题",
        help_text="选手看到的名称，用于列表/榜单展示。",
    )
    slug = forms.CharField(
        label="题目标识",
        help_text="URL/接口唯一标识，同一比赛下需唯一，建议使用英文/短横线。",
    )
    short_description = forms.CharField(
        required=False,
        label="题目简介",
        help_text="列表视图的简短摘要/提示，便于快速浏览筛选。",
    )
    content = forms.CharField(
        widget=forms.Textarea,
        label="题目内容",
        help_text="完整题面描述，包含环境信息、要求、附件说明等。",
    )

    class Meta:
        model = Challenge
        fields = "__all__"

# 后台注册：配置题目、分类与解题记录的 Django Admin 展示。


@admin.register(ChallengeCategory)
class ChallengeCategoryAdmin(admin.ModelAdmin):
    """题目分类后台：支持名称/slug 搜索与自动填充。"""
    # 列表展示字段
    list_display = ("name", "slug")
    # 支持按名称/slug 搜索
    search_fields = ("name", "slug")
    # 根据 name 自动生成 slug
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    form = ChallengeAdminForm
    """
    题目后台：按前缀 + 花括号 + Flag 值的输入方式展示。

    - 先录入基础信息与分值，再选择 Flag 类型与前缀/值，帮助出题人理解最终 Flag 结构。
    """
    # 列表展示标题、所属比赛与分值等
    list_display = ("title", "contest", "category", "difficulty", "base_points", "flag_type", "is_active")
    # 过滤器：按比赛、分类、难度、上线状态
    list_filter = ("contest", "category", "difficulty", "flag_type", "is_active")
    # 搜索：标题、slug、简介
    search_fields = ("title", "slug", "short_description")
    # 自动生成 slug
    prepopulated_fields = {"slug": ("title",)}
    # 表单字段提示
    field_help_texts = {
        "dynamic_prefix": "可选前缀，最终 Flag = 前缀 + '{' + Flag 值 + '}'；无需手写花括号。",
        "flag": "静态：填写完整 Flag 值；动态：填写种子，系统按赛题/解题人生成唯一值。",
        "flag_case_insensitive": "勾选后校验时不区分大小写。",
    }
    fieldsets = (
        (
            "基础信息",
            {
                "fields": (
                    "contest",
                    "category",
                    "title",
                    "slug",
                    "short_description",
                    "content",
                    "difficulty",
                    "is_active",
                )
            },
        ),
        (
            "分值配置",
            {
                "fields": ("base_points", "scoring_mode", "decay_type", "decay_factor", "min_score"),
                "description": "动态计分会按解出次数衰减至最低分；固定分值时衰减相关字段不会生效。",
            },
        ),
        (
            "Flag 配置",
            {
                "fields": ("dynamic_prefix", "flag_type", "flag", "flag_case_insensitive"),
                "description": "最终 Flag 由“前缀 + { + Flag 值 + }”自动拼接；静态填写完整 Flag 值，动态填写种子。",
            },
        ),
        (
            "附件管理",
            {
                "fields": ("upload_file", "existing_attachments"),
                "description": "选择文件后保存自动创建附件记录。",
            },
        ),
    )
    # 只读字段：附件列表
    readonly_fields = ("existing_attachments",)

    class Media:
        """后台表单静态资源：按计分模式动态显示衰减字段。"""
        js = ("challenges/js/challenge_admin.js",)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        for name, help_text in self.field_help_texts.items():
            if name in form.base_fields:
                form.base_fields[name].help_text = help_text
        return form

    def save_model(self, request, obj: Challenge, form, change):
        """
        保存题目后，如果有选择附件则上传并创建附件记录。
        """
        super().save_model(request, obj, form, change)
        upload = form.files.get("upload_file")
        if upload:
            try:
                service = AttachmentUploadService()
                schema = AttachmentUploadSchema(
                    contest_slug=obj.contest.slug,
                    challenge_slug=obj.slug,
                    filename=upload.name,
                )
                result = service.execute(schema, content=upload.read())
                ChallengeAttachmentRepo().create(
                    {
                        "challenge": obj,
                        "name": upload.name,
                        "url": result.get("url") or result.get("path"),
                        "order": obj.attachments.count() + 1,
                    }
                )
                messages.success(request, f"附件已上传：{upload.name}")
            except Exception as exc:  # pragma: no cover
                messages.error(request, f"上传附件失败：{exc}")

    @admin.display(description="已上传附件")
    def existing_attachments(self, obj: Challenge):
        """
        展示已上传的附件列表。
        """
        attachments = obj.attachments.all().order_by("order", "id")
        if not attachments:
            return "暂无附件"
        return format_html_join(
            "<br>",
            '<a href="{0}" target="_blank">{1}</a> (序号 {2})',
            [(att.url, att.name, att.order) for att in attachments],
        )


@admin.register(ChallengeSolve)
class ChallengeSolveAdmin(admin.ModelAdmin):
    """解题记录后台：查看得分与解题时间，保持只读。"""
    # 列表展示解题核心信息
    list_display = ("challenge", "user", "team", "awarded_points", "solved_at")
    # 过滤：按所属比赛
    list_filter = ("challenge__contest",)
    # 所有字段只读，防止后台修改历史记录
    readonly_fields = ("challenge", "user", "team", "awarded_points", "solved_at")

    def has_add_permission(self, request):
        """禁止后台新增解题记录，避免污染榜单。"""
        return False

    def has_change_permission(self, request, obj=None):
        """禁止后台编辑解题记录。"""
        return False

    def has_delete_permission(self, request, obj=None):
        """禁止后台删除解题记录。"""
        return False
