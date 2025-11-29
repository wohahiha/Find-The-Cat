from __future__ import annotations

from django.contrib import admin, messages
from django.db import models
from django.urls import reverse, path
from django.utils.html import format_html
from django.http import HttpResponseRedirect
from django.utils import timezone
from django.core.exceptions import PermissionDenied

from .models import Contest, Team, TeamMember, ContestAnnouncement, ContestScoreboard
from .services import ScoreboardService, determine_contest_status
from django import forms
from apps.common.infra.logger import get_logger, logger_extra
from apps.challenges.models import ChallengeCategory

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


class ContestAdminForm(forms.ModelForm):
    """比赛后台自定义表单：个人赛自动设置队伍人数为 1"""

    class Meta:
        model = Contest
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "max_team_members" in self.fields:
            self.fields["max_team_members"].required = False
            self.fields["max_team_members"].help_text = (
                "提示：个人赛固定为 1；比赛开始后人数只能增加不能减少。"
            )
        if "is_team_based" in self.fields:
            self.fields["is_team_based"].help_text = (
                "提示：比赛开始后不可再修改该选项，请在开赛前确认赛制。"
            )
        if "start_time" in self.fields:
            self.fields["start_time"].help_text = "提示：比赛开始后该时间不可再调整。"
        if "end_time" in self.fields:
            self.fields["end_time"].help_text = "提示：比赛结束后不允许修改结束时间。"
        if "freeze_time" in self.fields:
            self.fields["freeze_time"].help_text = "提示：封榜一旦生效或比赛结束将无法再调整。"
        self._original_is_team_based = getattr(self.instance, "is_team_based", True)
        self._original_max_members = getattr(self.instance, "max_team_members", 1)
        self._original_start_time = getattr(self.instance, "start_time", None)
        self._original_end_time = getattr(self.instance, "end_time", None)
        self._original_freeze_time = getattr(self.instance, "freeze_time", None)

    def clean(self):
        cleaned = super().clean()
        is_team_based = cleaned.get(
            "is_team_based",
            self._original_is_team_based if self.instance and self.instance.pk else cleaned.get("is_team_based"),
        )
        max_members = cleaned.get("max_team_members")
        if max_members is None and self.instance and self.instance.pk:
            max_members = self._original_max_members
            cleaned["max_team_members"] = max_members
        contest_started = bool(self.instance and self.instance.pk and self.instance.has_started)
        contest_finished = bool(self.instance and self.instance.pk and self.instance.has_ended)
        now = timezone.now()

        if self.instance and self.instance.pk:
            if "start_time" not in cleaned or cleaned.get("start_time") in (None, ""):
                cleaned["start_time"] = self._original_start_time
            if "end_time" not in cleaned or cleaned.get("end_time") in (None, ""):
                cleaned["end_time"] = self._original_end_time
            if "freeze_time" not in cleaned:
                cleaned["freeze_time"] = self._original_freeze_time

        if not is_team_based:
            cleaned["max_team_members"] = 1
        else:
            if max_members is None or int(max_members) < 1:
                raise forms.ValidationError("请为组队赛填写大于 0 的队伍人数上限")

        if contest_started:
            if is_team_based != self._original_is_team_based:
                raise forms.ValidationError("比赛已开始，无法修改是否组队赛")
            if (
                    is_team_based
                    and int(cleaned.get("max_team_members", 1)) < int(self._original_max_members or 1)
            ):
                raise forms.ValidationError("比赛已开始，队伍人数上限仅可增加不可减少")
            if cleaned.get("start_time") and cleaned.get("start_time") != self._original_start_time:
                raise forms.ValidationError("比赛已开始，无法调整开始时间")

        if contest_finished:
            if cleaned.get("end_time") and cleaned.get("end_time") != self._original_end_time:
                raise forms.ValidationError("比赛已结束，无法调整结束时间")

        freeze_locked = False
        if self.instance and self.instance.pk:
            if contest_finished:
                freeze_locked = True
            elif self.instance.freeze_time and now >= self.instance.freeze_time:
                freeze_locked = True
        if freeze_locked and cleaned.get("freeze_time") != self._original_freeze_time:
            raise forms.ValidationError("封榜时间已生效或比赛已结束，无法调整封榜时间")
        return cleaned


class ContestStatusFilter(admin.SimpleListFilter):
    """后台过滤器：按比赛状态筛选"""

    title = "状态"
    parameter_name = "status"

    def lookups(self, request, model_admin):
        return [
            ("not_started", "未开始"),
            ("running", "进行中"),
            ("frozen", "进行中（已封榜）"),
            ("ended", "已结束"),
        ]

    def queryset(self, request, queryset):
        value = self.value()
        if not value:
            return queryset
        now = timezone.now()
        if value == "not_started":
            return queryset.filter(start_time__gt=now)
        if value == "running":
            return (
                queryset.filter(start_time__lte=now, end_time__gt=now)
                .filter(models.Q(freeze_time__isnull=True) | models.Q(freeze_time__gt=now))
            )
        if value == "frozen":
            return queryset.filter(start_time__lte=now, end_time__gt=now, freeze_time__lte=now)
        if value == "ended":
            return queryset.filter(end_time__lte=now)
        return queryset


@admin.register(Contest)
class ContestAdmin(AdminAuditMixin, admin.ModelAdmin):
    """比赛模型后台展示：支持基础字段检索与过滤"""
    # 列表展示关键字段，便于运营查看时间与赛制
    list_display = (
        "id_display",
        "name",
        "slug",
        "visibility",
        "start_time",
        "end_time",
        "is_team_based",
        "status_display",
    )
    # 允许通过名称、slug 搜索
    search_fields = ("name", "slug")
    # 按可见性与赛制过滤
    list_filter = ("visibility", "is_team_based", ContestStatusFilter)
    # 根据 name 自动生成 slug
    prepopulated_fields = {"slug": ("name",)}
    # 只读字段：排行榜预览避免误编辑
    readonly_fields = ("scoreboard_preview", "view_teams_link", "view_scoreboard_link", "end_now_action")
    inlines = ()
    audit_model = "Contest"
    form = ContestAdminForm
    fieldsets = (
        (None, {"fields": ("name", "slug", "description", "visibility")}),
        ("时间与赛制", {"fields": ("start_time", "end_time", "freeze_time", "is_team_based", "max_team_members")}),
        ("队伍管理", {"fields": ("view_teams_link",), "description": ""}),
        (
            "排行榜",
            {
                "fields": ("scoreboard_preview", "view_scoreboard_link"),
                "description": "",
            },
        ),
    )

    def get_form(self, request, obj=None, **kwargs):
        """为比赛详情页字段追加帮助文字，降低配置歧义"""
        form = super().get_form(request, obj, **kwargs)
        help_texts = {
            "name": "前台显示的比赛名称",
            "slug": "比赛唯一标识，用于 URL 与接口访问，保存后谨慎修改",
            "description": "比赛简介或规则说明，支持富文本",
            "visibility": "选择公开/私有，私有比赛仅特定用户可见",
            "start_time": "比赛开始时间，影响报名/提交的可用性判断；开赛后不可调整此时间",
            "end_time": "比赛结束时间，截止后将禁止提交；比赛结束后不可再修改",
            "freeze_time": "可选封榜时间，封榜生效或比赛结束后不可再调整",
            "is_team_based": "开启为团队赛，否则为个人赛；比赛开始后不可修改",
            "max_team_members": "队伍最大人数限制，仅对组队赛生效；比赛开始后仅可增加不可减少",
        }
        for field_name, text in help_texts.items():
            if field_name in form.base_fields:
                form.base_fields[field_name].help_text = text

        return form

    def get_readonly_fields(self, request, obj=None):
        """根据状态动态控制只读字段"""
        base = list(super().get_readonly_fields(request, obj))
        if obj is None:
            for field in ("scoreboard_preview", "view_teams_link", "view_scoreboard_link"):
                if field in base:
                    base.remove(field)
            return tuple(base)

        if obj.has_started:
            for field in ("start_time", "is_team_based"):
                if field not in base:
                    base.append(field)
        if obj.has_ended:
            for field in ("end_time",):
                if field not in base:
                    base.append(field)
        if obj.has_ended or (obj.freeze_time and timezone.now() >= obj.freeze_time):
            if "freeze_time" not in base:
                base.append("freeze_time")
        return tuple(base)

    def get_fieldsets(self, request, obj=None):
        """仅在编辑页面展示排行榜与队伍相关字段"""
        if obj is None:
            return (
                (None, {"fields": ("name", "slug", "description", "visibility")}),
                ("时间与赛制",
                 {"fields": ("start_time", "end_time", "freeze_time", "is_team_based", "max_team_members")}),
            )
        fieldsets = list(super().get_fieldsets(request, obj))
        fieldsets.append(
            (
                "终止比赛",
                {
                    "fields": ("end_now_action",),
                    "description": "需要提前结束比赛时，可使用该按钮立即结束。",
                },
            )
        )
        return fieldsets

    def get_inline_instances(self, request, obj=None):
        """新增比赛时不显示队伍内联"""
        inline_instances = []
        for inline_class in self.inlines:
            inline_instances.append(inline_class(self.model, self.admin_site))
        return inline_instances

    def has_delete_permission(self, request, obj=None):
        """保持 Django 权限校验，具体禁止逻辑在 delete_model 中统一处理"""
        return super().has_delete_permission(request, obj)

    def delete_model(self, request, obj):
        """删除单个对象时校验状态，比赛进行中禁止删除并给出明确提示"""
        if obj and not obj.has_ended:
            self.message_user(request, "比赛尚在进行中，无法删除。请先结束比赛后再执行删除。", level=messages.ERROR)
            setattr(request, "_contest_delete_blocked", True)
            return
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        """批量删除前过滤掉未结束比赛"""
        now = timezone.now()
        blocked = queryset.filter(end_time__gt=now)
        if blocked.exists():
            messages.error(request, "部分比赛尚未结束，无法删除。请先结束比赛后再尝试。")
        allowed = queryset.exclude(pk__in=blocked.values_list("pk", flat=True))
        if not allowed.exists():
            if blocked.exists():
                setattr(request, "_contest_delete_blocked", True)
            return
        super().delete_queryset(request, allowed)

    def response_delete(self, request, obj_display, obj_id):
        """若删除被拦截则返回对象编辑页且不显示成功提示"""
        if getattr(request, "_contest_delete_blocked", False):
            setattr(request, "_contest_delete_blocked", False)
            if obj_id:
                change_url = reverse("admin:contests_contest_change", args=[obj_id])
            else:
                change_url = reverse("admin:contests_contest_changelist")
            return HttpResponseRedirect(change_url)
        return super().response_delete(request, obj_display, obj_id)

    def message_user(self, request, message, level=messages.INFO, extra_tags="", fail_silently=False):
        """阻止删除失败场景下的成功提示"""
        if getattr(request, "_contest_delete_blocked", False) and level >= messages.SUCCESS:
            setattr(request, "_contest_delete_blocked", False)
            return
        super().message_user(request, message, level=level, extra_tags=extra_tags, fail_silently=fail_silently)

    class Media:
        """后端表单交互：非组队赛隐藏队伍人数字段"""

        js = ("contests/js/contest_admin.js",)

    @admin.display(description="排行榜前 10 名")
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

    @admin.display(description="队伍列表", ordering=None)
    def view_teams_link(self, obj):
        """返回跳转到队伍列表的按钮"""
        if not obj or not obj.pk:
            return "保存比赛后可查看队伍"
        url = reverse("admin:contests_team_changelist")
        url = f"{url}?contest_id={obj.pk}"
        return format_html('<a class="button" href="{}" target="_blank">查看全部队伍</a>', url)

    @admin.display(description="完整排行榜", ordering=None)
    def view_scoreboard_link(self, obj):
        """跳转到排行榜后台入口"""
        if not obj or not obj.pk:
            return "保存比赛后可查看排行榜"
        url = reverse("admin:contests_contestscoreboard_change", args=[obj.pk])
        return format_html('<a class="button" href="{}" target="_blank">打开排行榜</a>', url)

    @admin.display(description="状态")
    def status_display(self, obj):
        return determine_contest_status(obj)

    @admin.display(description="ID", ordering="id")
    def id_display(self, obj):
        return obj.id

    @admin.display(description="立即结束")
    def end_now_action(self, obj):
        if not obj or obj.has_ended:
            return "比赛已结束"
        url = reverse("admin:contests_contest_end_now", args=[obj.pk])
        return format_html(
            '<a class="button" href="{}" onclick="return confirm(\'确认立即结束该比赛？\');">立即结束</a>',
            url,
        )

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<path:object_id>/end-now/",
                self.admin_site.admin_view(self.end_now_view),
                name="contests_contest_end_now",
            ),
        ]
        return custom + urls

    def end_now_view(self, request, object_id):
        contest = self.get_object(request, object_id)
        if contest is None:
            self.message_user(request, "未找到比赛", level=messages.ERROR)
            return HttpResponseRedirect(reverse("admin:contests_contest_changelist"))
        if not self.has_change_permission(request, contest):
            raise PermissionDenied
        redirect_url = reverse("admin:contests_contest_change", args=[contest.pk])
        if contest.has_ended:
            self.message_user(request, "比赛已结束，无需操作", level=messages.WARNING)
            return HttpResponseRedirect(redirect_url)
        now = timezone.now()
        contest.end_time = now
        if contest.freeze_time and contest.freeze_time > now:
            contest.freeze_time = now
        contest.save(update_fields=["end_time", "freeze_time", "updated_at"])
        self.message_user(request, "比赛已终止", level=messages.SUCCESS)
        return HttpResponseRedirect(redirect_url)


class ChallengeCategoryInline(admin.TabularInline):
    """比赛下题目分类：在比赛表单中直接维护"""

    model = ChallengeCategory
    fk_name = "contest"
    extra = 1
    min_num = 1
    validate_min = True
    fields = ("name", "slug", "description")
    readonly_fields = ()
    prepopulated_fields = {"slug": ("name",)}

    def has_delete_permission(self, request, obj=None):
        if obj and obj.has_started:
            return False
        return super().has_delete_permission(request, obj)

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        help_texts = {
            "name": "分类名称，用于题目分组与前台展示",
            "slug": "题目分类唯一标识，默认等同于名称",
            "description": "分类描述/备注信息，选填",
        }
        for name, text in help_texts.items():
            if name in formset.form.base_fields:
                formset.form.base_fields[name].help_text = text
        return formset


# 追加内联到比赛后台（仅题目分类）
ContestAdmin.inlines = ContestAdmin.inlines + (ChallengeCategoryInline,)  # type: ignore


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

    def changelist_view(self, request, extra_context=None):
        contest_id = request.GET.get("contest_id")
        if contest_id and "contest__id__exact" not in request.GET:
            params = request.GET.copy()
            params["contest__id__exact"] = params.pop("contest_id")
            return HttpResponseRedirect(f"{request.path}?{params.urlencode()}")
        return super().changelist_view(request, extra_context=extra_context)

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
