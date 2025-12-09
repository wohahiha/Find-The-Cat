"""
挑战模块后台配置：
- 提供题目/分类/解题记录的管理界面，支持附件上传、字段提示与只读控制
- 主要服务于运维/出题人后台操作，不参与前台业务逻辑
"""

from __future__ import annotations

from django.contrib import admin, messages
from django import forms
from django.urls import reverse, path
from django.http import JsonResponse
from django.utils import timezone
from apps.common.infra.logger import get_logger, logger_extra
from apps.contests.models import Contest
from apps.machines.models import ChallengeMachineConfig
from .models import ChallengeCategory, Challenge, ChallengeSolve, ChallengeAttachment
from .services import AttachmentUploadService
from .schemas import AttachmentUploadSchema
from .repo import ChallengeAttachmentRepo

logger = get_logger(__name__)


class AdminAuditMixin:
    """后台审计日志：记录增删改关键对象"""

    audit_model = ""

    def log_change(self, request, obj, message):
        super().log_change(request, obj, message)  # type: ignore[misc]
        logger.info(
            "Admin修改",
            extra=logger_extra(
                {
                    "admin": getattr(request.user, "username", None),
                    "model": self.audit_model or obj.__class__.__name__,
                    "object_id": getattr(obj, "pk", None),
                    "action": "change",
                }
            ),
        )

    def log_addition(self, request, obj, message):
        super().log_addition(request, obj, message)  # type: ignore[misc]
        logger.info(
            "Admin新增",
            extra=logger_extra(
                {
                    "admin": getattr(request.user, "username", None),
                    "model": self.audit_model or obj.__class__.__name__,
                    "object_id": getattr(obj, "pk", None),
                    "action": "add",
                }
            ),
        )

    def log_deletion(self, request, obj, object_repr):
        super().log_deletion(request, obj, object_repr)  # type: ignore[misc]
        logger.info(
            "Admin删除",
            extra=logger_extra(
                {
                    "admin": getattr(request.user, "username", None),
                    "model": self.audit_model or obj.__class__.__name__,
                    "object_repr": object_repr,
                    "action": "delete",
                }
            ),
        )


class ChallengeAdminForm(forms.ModelForm):
    """题目后台表单：追加附件上传按钮"""

    upload_file = forms.FileField(
        required=False,
        label="上传附件",
        help_text="选择本地文件，保存后自动上传并创建附件记录",
    )
    title = forms.CharField(
        label="题目标题",
        help_text="选手看到的名称，用于列表/榜单展示",
    )
    slug = forms.CharField(
        label="题目标识",
        help_text="URL/接口唯一标识，同一比赛下需唯一，建议使用英文/短横线",
    )
    short_description = forms.CharField(
        required=False,
        label="题目简介",
        help_text="列表视图的简短摘要/提示，便于快速浏览筛选",
    )
    content = forms.CharField(
        widget=forms.Textarea,
        label="题目内容",
        help_text="完整题面描述，包含环境信息、要求、附件说明等",
    )
    blood_bonus_points = forms.CharField(
        required=False,
        label="n血加分列表",
        help_text="仅在选择“加分”时有效，自动按血次生成输入行",
        widget=forms.HiddenInput(),
    )

    class Meta:
        model = Challenge
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 将 JSON 列表转为按行文本，便于录入
        bonus_list = self.instance.blood_bonus_points if getattr(self, "instance", None) else None
        if isinstance(bonus_list, list):
            self.initial["blood_bonus_points"] = "\n".join(str(item) for item in bonus_list)

    def clean_blood_bonus_points(self):
        """将换行/逗号分隔的加分转换为整数列表"""
        raw = self.cleaned_data.get("blood_bonus_points") or ""
        if isinstance(raw, list):
            return raw
        segments = [seg.strip() for seg in str(raw).replace(",", "\n").splitlines() if seg.strip()]
        result: list[int] = []
        for idx, seg in enumerate(segments, start=1):
            try:
                val = int(seg)
            except Exception:
                raise forms.ValidationError(f"第 {idx} 行需为整数")
            if val < 0:
                raise forms.ValidationError("加分需大于等于 0")
            result.append(val)
        return result

    def clean(self):
        """校验加分数量与 n 值一致，避免遗漏"""
        cleaned = super().clean()
        reward_type = cleaned.get("blood_reward_type")
        reward_count = int(cleaned.get("blood_reward_count") or 0)
        bonus_list = cleaned.get("blood_bonus_points") or []
        if reward_type == Challenge.BloodRewardType.BONUS and reward_count > 0:
            if len(bonus_list) < reward_count:
                raise forms.ValidationError("请填写足够的加分行数，与 n 血数量一致")
        return cleaned


# 后台注册：配置题目、分类与解题记录的 Django Admin 展示


@admin.register(ChallengeCategory)
class ChallengeCategoryAdmin(AdminAuditMixin, admin.ModelAdmin):
    """题目分类后台：支持名称/slug 搜索与自动填充"""
    list_select_related = ("contest",)
    # 列表展示字段
    list_display = ("name", "contest", "slug")
    # 支持按名称/slug 搜索
    search_fields = ("name", "slug", "contest__name", "contest__slug")
    list_filter = ("contest",)
    # 根据 name 自动生成 slug
    prepopulated_fields = {"slug": ("name",)}

    def get_form(self, request, obj=None, **kwargs):
        """为分类详情页字段添加说明，避免命名冲突"""
        form = super().get_form(request, obj, **kwargs)
        help_texts = {
            "contest": "分类所属比赛，仅能在该比赛下选择",
            "name": "分类名称，用于后台分组与前台展示",
            "slug": "分类标识，需唯一（同一比赛内），建议使用英文/短横线组合",
        }
        for name, text in help_texts.items():
            if name in form.base_fields:
                form.base_fields[name].help_text = text
        return form

    def get_model_perms(self, request):
        """
        隐藏独立菜单入口，但保留外键弹窗的使用能力，避免在导航栏出现单独板块
        """
        return {}


@admin.register(Challenge)
class ChallengeAdmin(AdminAuditMixin, admin.ModelAdmin):
    form = ChallengeAdminForm
    """
    题目后台：按前缀 + 花括号 + Flag 值的输入方式展示

    - 先录入基础信息与分值，再选择 Flag 类型与前缀/值，帮助出题人理解最终 Flag 结构
    """
    # 列表展示标题、所属比赛与分值等
    list_display = ("title", "contest", "category", "difficulty", "base_points", "flag_type", "is_active")
    # 过滤器：按比赛、分类、难度、上线状态
    class ContestFilter(admin.SimpleListFilter):
        """按正在进行中的比赛过滤"""

        title = "正在进行中的比赛"
        parameter_name = "contest_filter"

        def lookups(self, request, model_admin):
            now = timezone.now()
            contests = (
                Contest.objects.filter(start_time__lte=now, end_time__gte=now)
                .order_by("-start_time")
            )
            return [(str(c.id), c.name) for c in contests]  # type: ignore[attr-defined]

        def queryset(self, request, queryset):
            if self.value():
                return queryset.filter(contest_id=self.value())
            return queryset

    class CategoryFilter(admin.SimpleListFilter):
        """分类过滤：需先选择比赛，再显示该比赛下的分类"""

        title = "分类"
        parameter_name = "category"

        def lookups(self, request, model_admin):
            contest_id = request.GET.get(ChallengeAdmin.ContestFilter.parameter_name)
            if not contest_id:
                return []
            categories = (
                ChallengeCategory.objects.filter(contest_id=contest_id)
                .exclude(name__isnull=True)
                .exclude(name__exact="")
                .order_by("name")
            )
            return [(str(cat.id), cat.name) for cat in categories]  # type: ignore[attr-defined]

        def has_output(self) -> bool:
            # 无比赛选择时不展示分类过滤器
            return bool(self.lookup_choices)

        def queryset(self, request, queryset):
            if self.value():
                return queryset.filter(category_id=self.value())
            return queryset

    list_filter = (ContestFilter, CategoryFilter, "difficulty", "flag_type", "is_active")
    # 搜索：标题、slug、简介
    search_fields = ("title", "slug", "short_description")
    # 自动生成 slug
    prepopulated_fields = {"slug": ("title",)}
    # 表单字段提示
    field_help_texts = {
        "contest": "关联的比赛，影响榜单与计分范围",
        "category": "题目分类，便于后台筛选与前台分组展示",
        "difficulty": "题目难度标签，供出题人和选手参考",
        "base_points": "基础分值，动态模式下为起始分",
        "scoring_mode": "选择固定或动态计分，动态会随解出数量衰减",
        "decay_type": "动态计分衰减方式：百分比或线性递减",
        "decay_factor": "衰减系数，百分比模式填写 0-1，线性模式为每次递减分数",
        "min_score": "动态计分可衰减到的最低分，防止分值过低",
        "is_active": "关闭后选手不可见该题目，适合维护/下架",
        "dynamic_prefix": "可选前缀，最终 Flag = 前缀 + '{' + Flag 值 + '}'；无需手写花括号",
        "flag": "静态：填写完整 Flag 值；动态：填写种子（盐），系统生成唯一值",
        "flag_case_insensitive": "勾选后校验时不区分大小写",
        "blood_reward_type": "n 血奖励：无/加分/前 n 血不衰减（仅动态计分可选）",
        "blood_reward_count": "前 n 名解题享受奖励的数量，设置为 0 关闭",
        "blood_bonus_points": "仅在选择“加分”时填写，按行输入每一血的额外加分值",
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
                "description": "动态计分会按解出次数衰减至最低分；固定分值时衰减相关字段不会生效",
            },
        ),
        (
            "n血奖励",
            {
                "fields": ("blood_reward_type", "blood_reward_count", "blood_bonus_points"),
                "description": "配置前 n 名解题的加分或不衰减，不衰减仅支持动态分值",
            },
        ),
        (
            "Flag 配置",
            {
                "fields": ("dynamic_prefix", "flag_type", "flag", "flag_case_insensitive"),
                "description": "最终 Flag 由“前缀 + { + Flag 值 + }”自动拼接；静态填写完整 Flag 值，动态填写种子",
            },
        ),
        (
            "附件上传",
            {
                "fields": ("upload_file",),
                "description": "选择文件后保存自动创建附件记录，下方内联表可编辑/排序已有附件",
            },
        ),
    )
    readonly_fields = ()
    inlines = ()
    # 预取外键，避免列表页 N+1
    list_select_related = ("contest", "category", "author")
    audit_model = "Challenge"

    class Media:
        """后台表单静态资源：按计分模式动态显示衰减字段"""
        js = ("challenges/js/challenge_admin.js",)
        css = {
            "all": ("challenges/css/challenge_admin.css",),
        }

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        for name, help_text in self.field_help_texts.items():
            if name in form.base_fields:
                form.base_fields[name].help_text = help_text
        contest_id = self._get_contest_id(request, obj=obj)
        contest_field = form.base_fields.get("contest")
        if contest_field:
            contest_field.widget.attrs.setdefault(
                "data-category-url", reverse("admin:challenges_challenge_category_options")
            )
            if contest_id:
                contest_field.initial = contest_id
        category_field = form.base_fields.get("category")
        if category_field:
            if contest_id:
                category_field.queryset = ChallengeCategory.objects.filter(contest_id=contest_id)
                category_field.empty_label = "---------"
            else:
                category_field.queryset = ChallengeCategory.objects.none()
                category_field.empty_label = "请先选择比赛"
            initial_category = None
            if obj and obj.category_id:
                initial_category = obj.category_id
            elif request.POST.get("category"):
                initial_category = request.POST.get("category")
            if initial_category:
                category_field.widget.attrs["data-initial"] = str(initial_category)
            else:
                category_field.widget.attrs["data-initial"] = ""
        return form

    def save_model(self, request, obj: Challenge, form, change):
        """
        保存题目后，如果有选择附件则上传并创建附件记录
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
                        "order": obj.attachments.count() + 1,  # type: ignore[attr-defined]
                    }
                )
                messages.success(request, f"附件已上传：{upload.name}")
            except Exception as exc:  # pragma: no cover
                messages.error(request, f"上传附件失败：{exc}")

    def save_formset(self, request, form, formset, change):
        """
        保存内联对象时，确保靶机配置与题目绑定；附件自动补充排序
        """
        if getattr(formset, "model", None) is ChallengeMachineConfig:
            instances = formset.save(commit=False)
            for inline_obj in instances:
                inline_obj.challenge = form.instance
                inline_obj.save()
            for deleted in formset.deleted_objects:
                deleted.delete()
            formset.save_m2m()
            return
        if getattr(formset, "model", None) is ChallengeAttachment:
            instances = formset.save(commit=False)
            # 已有最大序号，便于新附件递增
            existing_max = (
                form.instance.attachments.order_by("-order", "-id").values_list("order", flat=True).first()
                if getattr(form.instance, "pk", None)
                else None
            )
            next_order = int(existing_max or 0)
            for inline_obj in instances:
                inline_obj.challenge = form.instance
                if not inline_obj.pk or not getattr(inline_obj, "order", None):
                    next_order += 1
                    inline_obj.order = next_order
                inline_obj.save()
            for deleted in formset.deleted_objects:
                deleted.delete()
            formset.save_m2m()
            return
        super().save_formset(request, form, formset, change)

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        contest_id = request.GET.get("contest")
        if contest_id:
            initial["contest"] = contest_id
        return initial

    def _get_contest_id(self, request, obj=None):
        contest_id = request.POST.get("contest") or request.GET.get("contest")
        if contest_id:
            return contest_id
        if obj:
            return obj.contest_id
        resolver = getattr(request, "resolver_match", None)
        if resolver and resolver.kwargs.get("object_id"):
            obj_id = resolver.kwargs["object_id"]
            return (
                Challenge.objects.filter(pk=obj_id)
                .values_list("contest_id", flat=True)
                .first()
            )
        return None

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "category-options/",
                self.admin_site.admin_view(self.category_options_view),
                name="challenges_challenge_category_options",
            ),
        ]
        return custom + urls

    def category_options_view(self, request):
        contest_id = request.GET.get("contest_id")
        results = []
        if contest_id:
            results = list(
                ChallengeCategory.objects.filter(contest_id=contest_id)
                .values("id", "name")
                .order_by("name", "id")
            )
        return JsonResponse({"results": results})


class MachineConfigInline(admin.StackedInline):
    """靶机配置内联：供出题人录入镜像/端口等模板信息"""

    model = ChallengeMachineConfig
    fk_name = "challenge"
    extra = 0
    min_num = 0
    can_delete = True
    validate_min = False
    max_num = 1
    verbose_name = "靶机配置"
    verbose_name_plural = "靶机配置"
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "image",
                    "container_port",
                    "max_instances_per_user",
                    "max_runtime_minutes",
                    "extend_minutes_default",
                    "extend_max_times",
                    "extend_threshold_minutes",
                    "clean_interval_seconds",
                    "port_cache_ttl",
                ),
                "description": "启用靶机后需要配置镜像、端口与运行时策略（实例数量、运行分钟数、延时策略、清理间隔、端口缓存）",
            },
        ),
        (
            "高级选项",
            {
                "fields": ("environment",),
                "classes": ("collapse",),
                "description": "可选环境变量（JSON 格式），启动实例时会传递给容器",
            },
        ),
    )


# 仅在定义完成后追加内联，保持 ChallengeAdmin 结构清晰
ChallengeAdmin.inlines = ChallengeAdmin.inlines + (MachineConfigInline,)  # type: ignore


class ChallengeAttachmentInline(admin.TabularInline):
    """附件内联：在题目页面直接查看/调整附件"""

    model = ChallengeAttachment
    fk_name = "challenge"
    extra = 0
    fields = ("name", "url")
    ordering = ("order", "id")
    verbose_name = "附件管理"
    verbose_name_plural = "附件管理"


# 将附件内联插入到现有 inline 列表前
ChallengeAdmin.inlines = (ChallengeAttachmentInline,) + ChallengeAdmin.inlines  # type: ignore


@admin.register(ChallengeSolve)
class ChallengeSolveAdmin(admin.ModelAdmin):
    """解题记录后台：查看得分与解题时间，保持只读"""
    list_select_related = ("challenge", "challenge__contest", "user", "team")
    # 列表展示解题核心信息
    list_display = ("challenge", "user", "team", "awarded_points", "bonus_points", "solved_at")
    # 过滤：按所属比赛
    list_filter = ("challenge__contest",)
    # 所有字段只读，防止后台修改历史记录
    readonly_fields = ("challenge", "user", "team", "awarded_points", "bonus_points", "solved_at")

    def get_form(self, request, obj=None, **kwargs):
        """为解题记录详情页字段添加说明，方便审计"""
        form = super().get_form(request, obj, **kwargs)
        help_texts = {
            "challenge": "对应的题目，决定分值与所属比赛",
            "user": "解题的用户，个人赛必填",
            "team": "解题所属队伍，组队赛使用",
            "awarded_points": "当次解题获得的总分值（已含动态衰减和加分）",
            "bonus_points": "若配置 n 血加分，则记录额外得分",
            "solved_at": "解题时间，用于榜单排序与血次序",
        }
        for name, text in help_texts.items():
            if name in form.base_fields:
                form.base_fields[name].help_text = text
        return form

    def has_add_permission(self, request):
        """禁止后台新增解题记录，避免污染榜单"""
        return False

    def has_change_permission(self, request, obj=None):
        """禁止后台编辑解题记录"""
        return False

    def has_delete_permission(self, request, obj=None):
        """禁止后台删除解题记录"""
        return False

    audit_model = "ChallengeCategory"

    def get_model_perms(self, request):
        """隐藏独立菜单入口，改为从比赛视角查看解题记录"""
        return {}
