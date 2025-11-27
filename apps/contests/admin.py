from __future__ import annotations

from django.contrib import admin

from .models import Contest, Team, TeamMember, ContestAnnouncement, ContestScoreboard
from apps.submissions.models import Submission
from .services import ScoreboardService
from django import forms
from apps.common.infra.logger import get_logger, logger_extra

# 后台注册：仅负责 Django Admin 展示配置，不包含业务逻辑

logger = get_logger(__name__)


class AdminAuditMixin:
    """后台审计日志：记录增删改关键对象"""

    audit_model = ""

    def log_change(self, request, object, message):
        super().log_change(request, object, message)
        logger.info(
            "Admin修改",
            extra=logger_extra(
                {
                    "admin": getattr(request.user, "username", None),
                    "model": self.audit_model or object.__class__.__name__,
                    "object_id": getattr(object, "pk", None),
                    "action": "change",
                }
            ),
        )

    def log_addition(self, request, object, message):
        super().log_addition(request, object, message)
        logger.info(
            "Admin新增",
            extra=logger_extra(
                {
                    "admin": getattr(request.user, "username", None),
                    "model": self.audit_model or object.__class__.__name__,
                    "object_id": getattr(object, "pk", None),
                    "action": "add",
                }
            ),
        )

    def log_deletion(self, request, object, object_repr):
        super().log_deletion(request, object, object_repr)
        logger.info(
            "Admin删除",
            extra=logger_extra(
                {
                    "admin": getattr(request.user, "username", None),
                    "model": self.audit_model or object.__class__.__name__,
                    "object_repr": object_repr,
                    "action": "delete",
                }
            ),
        )


class TeamMemberInline(admin.TabularInline):
    """队伍详情页内联成员管理：集中在队伍页编辑成员与角色"""

    model = TeamMember
    fk_name = "team"
    extra = 0
    fields = ("user", "role", "is_active", "joined_at")
    readonly_fields = ("joined_at",)
    raw_id_fields = ("user",)


class ContestAnnouncementAdminForm(forms.ModelForm):
    """比赛公告后台表单：内置字段说明，保证后台展示帮助文字"""

    class Meta:
        model = ContestAnnouncement
        fields = "__all__"
        help_texts = {
            "contest": "公告所属的比赛，保存后通常不修改",
            "title": "公告标题，前台列表将展示",
            "content": "公告正文，支持富文本/换行",
            "is_active": "关闭后公告对前台不可见，可用于下架旧公告",
            "created_at": "公告创建时间，供审计使用（只读）",
            "updated_at": "公告更新时间，便于追踪修改（只读）",
        }


@admin.register(Contest)
class ContestAdmin(AdminAuditMixin, admin.ModelAdmin):
    """比赛模型后台展示：支持基础字段检索与过滤"""
    # 列表展示关键字段，便于运营查看时间与赛制
    list_display = ("name", "slug", "visibility", "start_time", "end_time", "is_team_based")
    # 允许通过名称、slug 搜索
    search_fields = ("name", "slug")
    # 按可见性与赛制过滤
    list_filter = ("visibility", "is_team_based")
    # 根据 name 自动生成 slug
    prepopulated_fields = {"slug": ("name",)}
    # 只读字段：排行榜预览避免误编辑
    readonly_fields = ("scoreboard_preview",)
    inlines = ()
    audit_model = "Contest"
    fieldsets = (
        (None, {"fields": ("name", "slug", "description", "visibility")}),
        ("时间与赛制", {"fields": ("start_time", "end_time", "freeze_time", "is_team_based", "max_team_members")}),
        ("排行榜", {"fields": ("scoreboard_preview",), "description": "仅展示前 10 名供后台快速查看"}),
    )

    def get_form(self, request, obj=None, **kwargs):
        """为比赛详情页字段追加帮助文字，降低配置歧义"""
        form = super().get_form(request, obj, **kwargs)
        help_texts = {
            "name": "前台显示的比赛名称，需简洁明了",
            "slug": "比赛唯一标识，用于 URL 与接口访问，保存后谨慎修改",
            "description": "比赛简介或规则说明，支持富文本",
            "visibility": "选择公开/私有，私有比赛仅特定用户可见",
            "start_time": "比赛开始时间，影响报名/提交的可用性判断",
            "end_time": "比赛结束时间，截止后将禁止提交与组队操作",
            "freeze_time": "可选封榜时间，封榜后榜单不再实时更新",
            "is_team_based": "开启后使用队伍模式，否则为个人赛",
            "max_team_members": "队伍最大人数限制，仅对组队赛生效",
        }
        for field_name, text in help_texts.items():
            if field_name in form.base_fields:
                form.base_fields[field_name].help_text = text
        return form

    def scoreboard_preview(self, obj):
        """显示前 10 名排行榜，供后台查看"""
        if not obj or not obj.pk:
            return "请先保存比赛后再查看排行榜"
        service = ScoreboardService()
        board = service.execute(obj, ignore_freeze=True)[:10]
        if not board:
            return "暂无榜单数据"
        lines = []
        for entry in board:
            if entry.get("type") == "team":
                name = entry["team"]["name"]
            else:
                name = entry["user"]["username"]
            lines.append(f"#{entry['rank']} {name} - {entry['score']} 分")
        return "\n".join(lines)

    scoreboard_preview.short_description = "排行榜前 10 名"


class TeamInline(admin.TabularInline):
    """比赛下队伍管理：选中比赛后查看/调整队伍"""

    model = Team
    fk_name = "contest"
    extra = 0
    fields = ("name", "slug", "captain", "invite_token", "is_active", "created_at")
    readonly_fields = ("created_at",)
    prepopulated_fields = {"slug": ("name",)}


class SubmissionInline(admin.TabularInline):
    """比赛下的提交记录：只读查看，不允许修改"""

    model = Submission
    fk_name = "contest"
    extra = 0
    fields = ("challenge", "user", "team", "status", "is_correct", "awarded_points", "bonus_points", "blood_rank",
              "created_at")
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# 追加内联到比赛后台
ContestAdmin.inlines = ContestAdmin.inlines + (TeamInline, SubmissionInline)  # type: ignore


@admin.register(Team)
class TeamAdmin(AdminAuditMixin, admin.ModelAdmin):
    """队伍后台展示：展示队伍状态与邀请码"""
    list_select_related = ("contest", "captain")
    # 列表展示队伍与队长、邀请码等信息
    list_display = ("name", "contest", "captain", "is_active", "invite_token")
    # 支持按比赛与有效状态过滤
    list_filter = ("contest", "is_active")
    # 支持按名称/slug/邀请码搜索
    search_fields = ("name", "slug", "invite_token")
    # 根据名称预生成 slug
    prepopulated_fields = {"slug": ("name",)}
    # 队伍详情页内联成员编辑
    inlines = [TeamMemberInline]
    audit_model = "Team"

    def get_form(self, request, obj=None, **kwargs):
        """为队伍详情页字段追加帮助文字，避免误操作"""
        form = super().get_form(request, obj, **kwargs)
        help_texts = {
            "contest": "队伍所属的比赛，保存后不建议修改",
            "name": "队伍展示名称，同一比赛下需唯一",
            "slug": "队伍标识，用于 URL/接口访问，建议与名称一致的英文形式",
            "description": "队伍简介，供成员/管理员参考",
            "invite_token": "加入队伍的邀请码，重置后旧邀请码失效",
            "captain": "当前队长用户，变更后需同步团队沟通",
            "is_active": "关闭后队伍视为解散，成员关系不再生效",
        }
        for field_name, text in help_texts.items():
            if field_name in form.base_fields:
                form.base_fields[field_name].help_text = text
        return form

    def get_model_perms(self, request):
        """隐藏独立队伍板块，转由比赛内联管理"""
        return {}


@admin.register(ContestAnnouncement)
class ContestAnnouncementAdmin(AdminAuditMixin, admin.ModelAdmin):
    """比赛公告后台：支持发布、下架与修改内容"""

    form = ContestAnnouncementAdminForm
    list_select_related = ("contest",)
    list_display = ("contest", "title", "is_active", "created_at")
    list_filter = ("contest", "is_active", "created_at")
    search_fields = ("title", "contest__name", "contest__slug")
    ordering = ("-created_at",)
    audit_model = "ContestAnnouncement"

    def get_form(self, request, obj=None, **kwargs):
        """为公告字段添加帮助文字，方便运营编辑"""
        form = super().get_form(request, obj, **kwargs)
        help_texts = {
            "contest": "公告所属的比赛，保存后通常不修改",
            "title": "公告标题，前台列表将展示",
            "content": "公告正文，支持富文本/换行",
            "is_active": "关闭后公告对前台不可见，可用于下架旧公告",
            "created_at": "公告创建时间，供审计使用（只读）",
            "updated_at": "公告更新时间，便于追踪修改（只读）",
        }
        for field_name, text in help_texts.items():
            if field_name in form.base_fields:
                form.base_fields[field_name].help_text = text
        return form


@admin.register(ContestScoreboard)
class ContestScoreboardAdmin(AdminAuditMixin, admin.ModelAdmin):
    """
    比赛排行榜（后台专用，忽略封榜）：
    - 列表展示比赛及前 3 名
    - 详情页展示完整排行榜
    - 仅展示，不可新增/删除
    """

    list_display = ("name", "slug", "top1", "top2", "top3")
    search_fields = ("name", "slug")
    ordering = ("-start_time",)
    readonly_fields = ("name", "slug", "scoreboard_full")
    fields = ("name", "slug", "scoreboard_full")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        """排行榜后台仅供查看，不允许编辑"""
        return False

    def _board(self, obj) -> list[dict]:
        service = ScoreboardService()
        return service.execute(obj, ignore_freeze=True)

    def top1(self, obj):
        board = self._board(obj)
        return self._display_rank(board, 0)

    def top2(self, obj):
        board = self._board(obj)
        return self._display_rank(board, 1)

    def top3(self, obj):
        board = self._board(obj)
        return self._display_rank(board, 2)

    top1.short_description = "No.1"
    top2.short_description = "No.2"
    top3.short_description = "No.3"

    def _display_rank(self, board: list[dict], idx: int) -> str:
        if len(board) <= idx:
            return "-"
        entry = board[idx]
        if entry.get("type") == "team":
            return entry["team"]["name"]
        return entry["user"]["username"]

    def scoreboard_full(self, obj):
        """完整排行榜（忽略封榜），供后台查看"""
        board = self._board(obj)
        if not board:
            return "暂无榜单数据"
        lines = []
        for entry in board:
            if entry.get("type") == "team":
                name = entry["team"]["name"]
            else:
                name = entry["user"]["username"]
            lines.append(f"#{entry['rank']} {name} - {entry['score']} 分")
        return "\n".join(lines)

    scoreboard_full.short_description = "完整排行榜"
