"""
后台账户管理配置与表单定义：
- 业务场景：Django Admin 管理用户、管理员、发信账号、验证码
- 模块角色：统一后台表单/列表/权限展示与校验，避免越权与误操作
- 功能：自定义登录提示、锁定账号类型、分配默认分组、权限概览、只读控制
"""

from __future__ import annotations

from django.contrib import admin
from django.contrib.admin.sites import NotRegistered
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
from django.utils import timezone
from django.db import models
from django import forms
from uuid import uuid4
from pathlib import Path

# 账号权限工具：分配默认权限组、校验内置分组
from apps.accounts.utils import (
    assign_default_admin_permissions,
    assign_default_user_permissions,
    ensure_builtin_groups,
)
# 全局权限常量与标签转换工具
from apps.common.permission_sets import (
    DEFAULT_ADMIN_GROUP,
    DEFAULT_USER_GROUP,
    PERMISSION_ITEMS,
    get_permission_label,
)
from apps.common.infra.logger import get_logger
from apps.common.infra.file_storage import default_storage
from apps.common.utils.validators import validate_image_file
from apps.common.ws_utils import broadcast_force_logout
from apps.contests.models import Contest, ContestParticipant
from .models import (
    PlayerUser,
    StaffUser,
    User,
)

# 注意：MailAccount 模型已迁移至 apps.system 模块
# 邮件账号在后台的 SYSTEM → 发信账号 中管理

logger = get_logger(__name__)
_VERB_MAP = {
    "add": "添加",
    "change": "修改",
    "delete": "删除",
    "view": "查看",
}


def _permission_label(perm, verb_map: dict[str, str]) -> str:
    """
    将权限对象转换为中文标签，未定义时根据 codename 回退
    """
    perm_code = f"{perm.content_type.app_label}.{perm.codename}"
    label = get_permission_label(perm_code)
    if label == perm_code:
        parts = perm.codename.split("_", 1)
        verb = parts[0]
        obj = parts[1] if len(parts) > 1 else perm.codename
        verb_cn = verb_map.get(verb, verb)
        model_class = perm.content_type.model_class()
        model_name = str(getattr(getattr(model_class, "_meta", None), "verbose_name", "")) or obj
        label = f"{model_name}-{verb_cn}"
    return label


def _filter_biz_permissions(queryset):
    """过滤仅保留业务权限，剔除 Django 内置 CRUD 权限"""
    codes = {(item.app_label, item.codename) for item in PERMISSION_ITEMS}
    q = models.Q()
    for app, code in codes:
        q |= models.Q(content_type__app_label=app, codename=code)
    if q.children:
        return queryset.filter(q, content_type__model="bizperm").distinct()
    return queryset.none()


def _label_biz_permission(perm):
    """业务权限中文标签生成"""
    return _permission_label(perm, _VERB_MAP)


def _maybe_force_logout(old_obj: User | None, new_obj: User) -> None:
    """判断是否需要强制下线：停用账号或权限集合变更"""
    if not old_obj:
        return
    reason = None
    if old_obj.is_active and not new_obj.is_active:
        reason = "账户已被停用"
    else:
        try:
            old_perms = set(old_obj.get_all_permissions())
            new_perms = set(new_obj.get_all_permissions())
            if old_perms != new_perms:
                reason = "权限已变更，请重新登录"
        except (TypeError, ValueError):
            reason = None
    if reason:
        try:
            broadcast_force_logout(new_obj.id, reason=reason)  # type: ignore[attr-defined]
        except RuntimeError:
            # WebSocket 推送失败不阻断后台操作
            pass


class ActiveContestUserFilter(admin.SimpleListFilter):
    """按比赛筛选正在参赛的普通用户"""

    title = "正在进行的比赛"
    parameter_name = "active_contest"

    def lookups(self, request, model_admin):
        now = timezone.now()
        contests = Contest.objects.filter(start_time__lte=now, end_time__gt=now).order_by("-start_time")
        return [(str(c.id), c.name) for c in contests]  # type: ignore[attr-defined]

    def has_output(self) -> bool:
        """
        即使没有进行中的比赛也展示过滤器，方便运营确认筛选条件
        """
        return True

    def choices(self, changelist):
        """
        在无可选比赛时提示“暂无进行中的比赛”，避免下拉为空导致困惑
        """
        for choice in super().choices(changelist):
            yield choice
        if not self.lookup_choices:
            yield {
                "selected": False,
                "query_string": changelist.get_query_string({self.parameter_name: None}, []),
                "display": "暂无进行中的比赛",
            }

    def queryset(self, request, queryset):
        if self.value():
            return (
                queryset.filter(
                    contest_participations__contest_id=self.value(),
                    contest_participations__status=ContestParticipant.Status.RUNNING,
                    contest_participations__is_valid=True,
                )
                .distinct()
            )
        return queryset


class CompletedContestUserFilter(admin.SimpleListFilter):
    """按历史已完赛的比赛筛选用户"""

    title = "已完赛的比赛"
    parameter_name = "completed_contest"

    def lookups(self, request, model_admin):
        now = timezone.now()
        contests = Contest.objects.filter(end_time__lte=now).order_by("-end_time")
        return [(str(c.id), c.name) for c in contests]  # type: ignore[attr-defined]

    def has_output(self) -> bool:
        return True

    def choices(self, changelist):
        for choice in super().choices(changelist):
            yield choice
        if not self.lookup_choices:
            yield {
                "selected": False,
                "query_string": changelist.get_query_string({self.parameter_name: None}, []),
                "display": "暂无已完赛的比赛",
            }

    def queryset(self, request, queryset):
        if self.value():
            return (
                queryset.filter(
                    contest_participations__contest_id=self.value(),
                    contest_participations__status=ContestParticipant.Status.FINISHED,
                    contest_participations__is_valid=True,
                )
                .distinct()
            )
        return queryset


class AdminAuditMixin:
    """
    后台审计日志：记录增删改关键对象

    符合FTC日志标准，自动包含：
    - username: 从请求上下文自动获取
    - account_id: 从请求上下文自动获取
    - ip_address: 从请求上下文自动获取
    - 操作详情：模型名、对象ID、操作类型
    """

    audit_model = ""

    def log_change(self, request, obj: models.Model, message: str):
        """记录修改操作"""
        super().log_change(request, obj, message)  # type: ignore[misc]
        model_name = self.audit_model or obj.__class__.__name__
        object_id = getattr(obj, "pk", None)
        logger.info(f"管理员修改{model_name}对象 (ID={object_id}): {message}")

    def log_addition(self, request, obj: models.Model, message: str):
        """记录新增操作"""
        super().log_addition(request, obj, message)  # type: ignore[misc]
        model_name = self.audit_model or obj.__class__.__name__
        object_id = getattr(obj, "pk", None)
        logger.info(f"管理员创建{model_name}对象 (ID={object_id}): {message}")

    def log_deletion(self, request, obj: models.Model, object_repr: str):
        """记录删除操作"""
        super().log_deletion(request, obj, object_repr)  # type: ignore[misc]
        model_name = self.audit_model or obj.__class__.__name__
        logger.info(f"管理员删除{model_name}对象: {object_repr}")


class FTCAdminAuthenticationForm(AdminAuthenticationForm):
    """
    后台登录表单：替换默认 inactive 提示，向管理员展示中文失效说明

    - 继承 AdminAuthenticationForm，保持其校验逻辑
    - 仅覆盖 error_messages["inactive"]，让失效账户的提示更直观
    """
    error_messages = {
        **AdminAuthenticationForm.error_messages,
        "inactive": "账户失效，请联系管理员",
    }


# 将后台登录表单替换为自定义版本，提供中文的账户失效提示
admin.site.login_form = FTCAdminAuthenticationForm


class BaseAccountChangeForm(UserChangeForm):
    """
    账户变更表单基类：统一邮箱必填与默认分组校验

    - 子类通过 enforce_account_flags 写入账号类型与权限标志
    """

    avatar_upload = forms.FileField(
        required=False,
        label="上传头像文件",
        help_text="支持 PNG/JPEG/WEBP，上传后自动覆盖头像 URL",
    )

    def __init__(self, *args, **kwargs):
        """初始化时标记邮箱必填并确保默认分组存在"""
        super().__init__(*args, **kwargs)
        if "email" in self.fields:
            self.fields["email"].required = True
        ensure_builtin_groups()

    def enforce_account_flags(self, cleaned: dict) -> dict:
        """子类需实现：写入 account_type/is_staff/is_superuser 标志，保证身份不被篡改"""
        return cleaned

    def clean(self):
        """调用子类钩子写入账号标志，保持统一清洗流程"""
        cleaned = super().clean()
        avatar_file = cleaned.get("avatar_upload")
        if avatar_file:
            validate_image_file(avatar_file, allowed_types={"image/png", "image/jpeg", "image/webp"}, max_size_mb=2)
        return self.enforce_account_flags(cleaned)


class PlayerUserChangeForm(BaseAccountChangeForm):
    """
    普通用户变更表单：强制保持普通用户身份

    - 锁定 account_type=USER，防止后台编辑误将用户提升为管理员
    - 强制邮箱必填，满足通知/找回密码场景
    - 初始化时确保内置默认权限分组存在，避免保存时报组缺失
    """

    class Meta(UserChangeForm.Meta):  # type: ignore[misc]
        """表单元信息：绑定 PlayerUser 模型并开放全部字段供后台编辑"""
        model = PlayerUser
        fields = "__all__"

    def enforce_account_flags(self, cleaned: dict) -> dict:
        """锁定普通用户身份并关闭后台权限标志"""
        cleaned["account_type"] = User.AccountType.USER
        cleaned["is_staff"] = False
        cleaned["is_superuser"] = False
        return cleaned


class BaseAccountCreationForm(UserCreationForm):
    """
    账户创建表单基类：统一字段范围与账号标志写入
    """

    class Meta(UserCreationForm.Meta):  # type: ignore[misc]
        """表单元信息：创建账户时仅采集用户名和邮箱"""
        model = User
        fields = ("username", "email")

    def set_account_flags(self, user: User) -> User:
        """子类覆盖账号类型与权限标志设置"""
        return user

    def save(self, commit: bool = True):
        """
        保存时调用 set_account_flags，保持账号标志一致
        """
        user = super().save(commit=False)
        user = self.set_account_flags(user)
        if commit:
            user.save()
        return user


class PlayerUserCreationForm(BaseAccountCreationForm):
    """
    普通用户创建表单：控制创建流程中的权限标志

    - Meta 限定仅可填写用户名与邮箱，减少误填字段
    - save 时补充 account_type 与权限标志，确保最小权限
    """

    class Meta(UserCreationForm.Meta):  # type: ignore[misc]
        """表单元信息：创建普通用户时仅采集用户名和邮箱"""
        model = PlayerUser
        fields = ("username", "email")

    def set_account_flags(self, user: User) -> User:
        """写入普通用户标志"""
        user.account_type = User.AccountType.USER
        user.is_staff = False
        user.is_superuser = False
        return user


class StaffUserChangeForm(BaseAccountChangeForm):
    """
    管理员变更表单：保持管理员身份并清理队伍信息

    - 强制 account_type=ADMIN，避免被降级
    - 清空团队字段，确保管理员不混入队伍角色
    """

    class Meta(UserChangeForm.Meta):  # type: ignore[misc]
        """表单元信息：绑定 StaffUser 模型并开放全部字段供后台编辑"""
        model = StaffUser
        fields = "__all__"

    def enforce_account_flags(self, cleaned: dict) -> dict:
        """锁定管理员身份与后台登录标志"""
        cleaned["account_type"] = User.AccountType.ADMIN
        cleaned["is_staff"] = True
        return cleaned


class StaffUserCreationForm(BaseAccountCreationForm):
    """
    管理员创建表单：限制创建时的权限范围

    - 默认不开放团队字段，专注账户本身
    - save 时写入管理员标志，强制 is_superuser=False，防止误授超级管理员
    - 注意：通过此表单创建的管理员不是超级管理员
    - 超级管理员（account_id 1-10，最多10个）只能通过命令行创建：
      python manage.py createsuperuser
    """

    class Meta(UserCreationForm.Meta):  # type: ignore[misc]
        """表单元信息：创建管理员时仅采集用户名和邮箱"""
        model = StaffUser
        fields = ("username", "email")

    def set_account_flags(self, user: User) -> User:
        """写入管理员标志并默认关闭超管"""
        user.account_type = User.AccountType.ADMIN
        user.is_staff = True
        user.is_superuser = False
        return user


class BaseUserAdmin(DjangoUserAdmin):
    """
    用户后台公共配置：统一字段布局、权限展示及搜索配置

    - fieldsets：分区展示基础信息、个人信息、账户状态
    - readonly_fields：保护登录时间等审计字段，以及权限展示字段
    - add_fieldsets：新增用户时的字段布局，保持表单简洁
    - list_display/search_fields：统一列表展示与搜索入口
    """

    def get_form(self, request, obj=None, **kwargs):
        """
        获取后台表单时统一设置密码字段的中文标签
        """
        form = super().get_form(request, obj, **kwargs)
        password_field = form.base_fields.get("password")
        if password_field:
            password_field.label = "密码"
        # 为详情页字段添加简洁帮助文字，方便管理员理解含义
        help_texts = {
            "username": "唯一的登录名，保存后不可随意修改",
            "email": "用于找回密码、通知等场景，必须唯一有效",
            "account_id": "账户ID（自动分配，不可修改）：1-10超管，11-1000管理员，1001+普通用户",
            "nickname": "展示用昵称，前台显示使用",
            "avatar": "用户头像文件，留空则显示默认头像",
            "bio": "个人简介，前台资料页展示",
            "organization": "所属机构或学校，便于统计展示",
            "country": "国家/地区信息，便于榜单展示",
            "website": "个人站点或博客链接，需包含 http/https",
            "is_email_verified": "标记邮箱是否通过验证码验证",
            "is_active": "关闭后用户无法登录，保留数据",
            "groups": "后台权限组，决定可访问的模块与操作范围",
            "user_permissions": "细粒度权限，补充或覆盖所属用户组权限",
            "password": "存储加密后的密码，修改请使用\"更改密码\"表单",
        }
        for field_name, text in help_texts.items():
            if field_name in form.base_fields:
                form.base_fields[field_name].help_text = text
        return form

    # 详情页字段布局：基础信息/个人信息/状态
    fieldsets = (
        ("基础信息", {"fields": ("username", "password", "email", "account_id")}),
        (
            "个人信息",
            {
                "fields": (
                    "nickname",
                    "display_avatar_preview",
                    "avatar_upload",
                    "bio",
                    "organization",
                    "country",
                    "website",
                    "is_email_verified",
                )
            },
        ),
        (
            "账户状态",
            {
                "fields": ("is_active", "display_last_login", "display_date_joined"),
            },
        ),
    )
    # 只读字段：登陆时间/注册时间/账户ID与权限汇总，避免被编辑
    readonly_fields = (
        "account_id",
        "display_last_login",
        "display_date_joined",
        "display_effective_permissions",
        "display_avatar_preview",
    )
    # 新增表单布局：限制字段，降低误填
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "email", "password1", "password2"),
            },
        ),
    )
    # 列表展示：核心身份信息 + 状态
    list_display = (
        "display_username",
        "account_id",
        "display_email",
        "nickname",
        "display_active",
        "display_email_verified",
    )
    # 搜索入口
    search_fields = ("username", "email", "nickname")

    def get_readonly_fields(self, request, obj=None):
        """
        根据当前管理员权限动态决定只读字段

        - 非超级管理员：禁止修改用户名；统一禁止修改 is_superuser
        - 使用 dict.fromkeys 去重，避免重复追加
        """
        # request: 当前执行后台操作的管理员请求对象
        # obj: 正在编辑的用户实例，None 表示新建（此时无需追加权限概览）
        readonly = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:
            readonly.append("username")
        readonly.append("is_superuser")
        return tuple(dict.fromkeys(readonly))

    def get_fieldsets(self, request, obj=None):
        """
        编辑页追加“权限概览”区块，便于审计；新建时不展示
        """
        # request: 当前管理员请求
        # obj: 正在查看/编辑的用户，为 None 表示新建
        fieldsets = list(super().get_fieldsets(request, obj))
        if obj:
            fieldsets.append(
                (
                    "权限概览",
                    {"fields": ("display_effective_permissions",)},
                )
            )
        return fieldsets

    @admin.display(description="上次登录")
    def display_last_login(self, obj: User | None):
        """只读展示上次登录时间"""
        return obj.last_login if obj else None

    @admin.display(description="加入日期")
    def display_date_joined(self, obj: User | None):
        """只读展示加入时间"""
        return obj.date_joined if obj else None

    @admin.display(boolean=True, description="超级用户状态")
    def display_is_superuser(self, obj: User | None):
        """只读展示超级用户标志"""
        return obj.is_superuser if obj else False

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        """
        为关键字段提供中文标签，降低后台理解成本
        """
        # db_field: 模型字段对象，用于生成表单字段
        # request: 当前管理员请求
        # kwargs: 透传给父类的其他表单参数
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if field:
            if db_field.name == "username":
                field.label = "用户名"
            elif db_field.name == "password":
                field.label = "密码"
            elif db_field.name == "is_staff":
                field.label = "管理员"
            elif db_field.name == "is_active":
                field.label = "有效"
            elif db_field.name == "is_superuser":
                field.label = "超级用户状态"
            elif db_field.name == "last_login":
                field.label = "上次登录"
            elif db_field.name == "date_joined":
                field.label = "加入日期"
        return field

    @admin.display(description="头像预览")
    def display_avatar_preview(self, obj: User | None):
        """
        后台展示头像预览：若有头像 URL，展示 64px 方图并附加链接；否则显示“未设置”
        """
        avatar = getattr(obj, "avatar", "") if obj else ""
        if not avatar:
            return "未设置"
        img_html = f'<img src="{avatar}" alt="avatar" style="max-height:64px;max-width:64px;border-radius:6px;" />'
        return mark_safe(f'{img_html}<br><a href="{avatar}" target="_blank">查看原图</a>')

    def formfield_for_manytomany(self, db_field, request=None, **kwargs):
        """
        为权限多选字段添加中文标签，方便快速勾选
        """
        # db_field: 多对多字段（此处关注 user_permissions）
        # request: 当前管理员请求（可为空，兼容 Django 调用）
        # kwargs: 额外表单配置，保持透传
        field = super().formfield_for_manytomany(db_field, request=request, **kwargs)
        if not field:
            return field

        if db_field.name in ("user_permissions", "permissions"):
            field.label = "用户权限" if db_field.name == "user_permissions" else "权限列表"
            field.queryset = _filter_biz_permissions(field.queryset)
            field.label_from_instance = _label_biz_permission

        if db_field.name == "groups":
            field.label = "用户组"
        return field

    @admin.display(description="实际权限")
    def display_effective_permissions(self, obj: User | None):
        """
        以换行形式展示用户拥有的权限集合

        - 未保存对象返回“保存后可见”，避免空列表误解
        - 仅展示业务权限（PERMISSION_ITEMS），隐藏 Django 默认模型增删改查权限
        - 按模块（第一个“-”之前的片段）分组展示，便于审计
        """
        # obj: 当前后台正在查看的用户实例，为 None 表示新建（无权限集）
        if not obj:
            return "保存后可见"
        # 仅保留业务权限
        biz_codes = {f"{item.app_label}.{item.codename}" for item in PERMISSION_ITEMS}
        perms = sorted(
            get_permission_label(code) for code in obj.get_all_permissions() if code in biz_codes
        )
        if not perms:
            return "暂无"
        # 将权限按“大类-子类-动作”分组：首段为大类，次段为子类，其余合并为动作
        grouped: dict[str, dict[str, list[str]]] = {}
        for label in perms:
            parts = [p.strip() for p in label.split("-") if p.strip()]
            category = parts[0] if parts else "其他"
            subcategory = parts[1] if len(parts) > 1 else "通用"
            action = "-".join(parts[2:]) if len(parts) > 2 else (parts[1] if len(parts) == 2 else parts[0])
            grouped.setdefault(category, {}).setdefault(subcategory, []).append(action)
        # 构造 HTML：大类加粗，子类缩进，动作以顿号分隔
        lines = []
        for category in sorted(grouped.keys()):
            sub_map = grouped[category]
            sub_lines = []
            for sub in sorted(sub_map.keys()):
                actions = "、".join(sub_map[sub])
                sub_lines.append(f"&nbsp;&nbsp;• {sub}：{actions}")
            lines.append(f"<strong>{category}</strong><br>" + "<br>".join(sub_lines))
        return mark_safe("<br>".join(lines))

    # admin.display：布尔展示账号有效状态并提供中英列名
    @admin.display(boolean=True, description="有效")
    def display_active(self, obj: User) -> bool:
        """列表显示账号有效状态，便于快速筛选停用账号"""
        return obj.is_active

    # admin.display：布尔展示邮箱验证状态并提供中文列名
    @admin.display(boolean=True, description="邮箱验证")
    def display_email_verified(self, obj: User) -> bool:
        """列表显示邮箱是否已完成验证"""
        return obj.is_email_verified

    @admin.display(description="用户名")
    def display_username(self, obj: User) -> str:
        return obj.username

    @admin.display(description="邮箱")
    def display_email(self, obj: User) -> str:
        return obj.email


# @admin.register：将普通用户的管理配置注册到后台站点
@admin.register(PlayerUser)
class PlayerUserAdmin(AdminAuditMixin, BaseUserAdmin):
    """
    普通用户后台管理：

    - 仅管理 account_type=USER 的数据，避免与管理员混淆
    - 保存时自动分配默认用户组，确保基础权限
    - 控制增删改权限，仅 staff 可操作
    """

    add_form = PlayerUserCreationForm
    form = PlayerUserChangeForm
    # add_fieldsets：后台新增普通用户的字段布局（含用户名、邮箱、密码与权限）
    add_fieldsets = (
        (None, {"fields": ("username", "email", "password1", "password2")}),
        (
            "权限",
            {
                "fields": ("groups", "user_permissions"),
            },
        ),
    )
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "参赛信息",
            {
                "fields": (
                    "display_running_contests",
                    "display_registered_contests",
                    "display_finished_contests",
                ),
            },
        ),
        (
            "权限",
            {
                "fields": ("groups", "user_permissions"),
            },
        ),
    )
    # 列表字段：沿用基础展示并追加“正在参赛”
    list_display = BaseUserAdmin.list_display + ("display_running_contests",)
    # 过滤条件：按有效/邮箱验证/比赛筛选
    list_filter = ("is_active", "is_email_verified", ActiveContestUserFilter, CompletedContestUserFilter)
    # 只读字段：追加参赛汇总展示
    readonly_fields = BaseUserAdmin.readonly_fields + (
        "display_running_contests",
        "display_registered_contests",
        "display_finished_contests",
    )
    audit_model = "PlayerUser"

    def get_queryset(self, request):
        """
        仅返回普通用户的查询集

        - 通过 account_type 过滤，确保管理视图不混入管理员数据
        """
        # request: 当前后台管理员请求，用于权限与审计
        qs = super().get_queryset(request)
        return qs.filter(account_type=User.AccountType.USER)

    def has_change_permission(self, request, obj=None):
        """
        控制修改权限：仅 staff 可修改普通用户

        - 非 staff 直接拒绝，防止低权限后台账号修改他人信息
        """
        # request: 当前后台管理员请求
        # obj: 正在编辑的用户记录，None 表示列表页
        if not request.user.is_staff:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        """
        控制删除权限：仅 staff 可删除普通用户
        """
        # request: 当前后台管理员请求
        # obj: 正在删除的用户记录
        if not request.user.is_staff:
            return False
        return super().has_delete_permission(request, obj)

    def has_add_permission(self, request):
        """
        控制新增权限：仅 staff 可在后台创建普通用户
        """
        # request: 当前后台管理员请求
        return request.user.is_staff

    def save_model(self, request, obj: StaffUser, form, change):
        """
        保存时锁定普通用户身份并自动分配默认用户组

        - account_type 固定 USER，关闭 staff/superuser 防止越权
        - 若未选择分组，自动赋予 DEFAULT_USER_GROUP，保障基础权限
        """
        # request: 当前后台管理员请求
        # obj: 正在保存的用户实例
        # form: 管理后台提交的表单对象
        # change: 是否为编辑模式（True 编辑 / False 新建）
        old_obj = None
        if change and obj.pk:
            try:
                old_obj = obj.__class__.objects.get(pk=obj.pk)
            except obj.__class__.DoesNotExist:
                old_obj = None
        # 头像上传：若后台上传文件则保存并覆盖头像 URL
        avatar_file = form.cleaned_data.get("avatar_upload") if form else None
        if avatar_file:
            suffix = Path(getattr(avatar_file, "name", "") or "").suffix.lower()
            suffix = suffix if suffix in (".png", ".jpg", ".jpeg", ".webp") else ""
            if not suffix:
                ct_map = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
                suffix = ct_map.get(getattr(avatar_file, "content_type", ""), ".png")
            filename = f"admin_avatar_user_{getattr(obj, 'pk', 'u')}_{uuid4().hex}{suffix}"
            content = avatar_file.read()
            _, url = default_storage.save_bytes(content=content, filename=filename, subdir="avatars")
            obj.avatar = url or obj.avatar
        obj.account_type = User.AccountType.USER
        obj.is_staff = False
        obj.is_superuser = False
        super().save_model(request, obj, form, change)
        if not obj.groups.exists():
            assign_default_user_permissions(obj)
        try:
            obj_refreshed = obj.__class__.objects.get(pk=obj.pk)
        except obj.__class__.DoesNotExist:
            obj_refreshed = obj
        _maybe_force_logout(old_obj, obj_refreshed)

    @staticmethod
    def _build_participation_map(obj: PlayerUser) -> dict[str, list[str]]:
        """构造比赛参与分组：报名/进行中/已结束（仅展示有效记录）"""
        grouped = {
            ContestParticipant.Status.REGISTERED: [],
            ContestParticipant.Status.RUNNING: [],
            ContestParticipant.Status.FINISHED: [],
        }
        qs = obj.contest_participations.select_related("contest").filter(is_valid=True)  # type: ignore[attr-defined]
        for record in qs:
            contest_name = record.contest.name
            grouped.setdefault(record.status, []).append(contest_name)
        return grouped

    @admin.display(description="正在参赛")
    def display_running_contests(self, obj: PlayerUser) -> str:
        """列表页/详情：展示正在参赛的比赛名称"""
        grouped = self._build_participation_map(obj)
        running = grouped.get(ContestParticipant.Status.RUNNING) or []
        return mark_safe("、".join(running) if running else "无")

    @admin.display(description="已报名（未开赛）")
    def display_registered_contests(self, obj: PlayerUser) -> str:
        grouped = self._build_participation_map(obj)
        names = grouped.get(ContestParticipant.Status.REGISTERED) or []
        return mark_safe("、".join(names) if names else "无")

    @admin.display(description="已完赛")
    def display_finished_contests(self, obj: PlayerUser) -> str:
        grouped = self._build_participation_map(obj)
        names = grouped.get(ContestParticipant.Status.FINISHED) or []
        return mark_safe("、".join(names) if names else "无")

    def get_changeform_initial_data(self, request):
        """
        初始化变更表单时预填默认用户组，减少手工勾选
        """
        # request: 当前后台管理员请求
        initial = super().get_changeform_initial_data(request)
        default_group = Group.objects.filter(name=DEFAULT_USER_GROUP).first()
        if default_group and "groups" not in initial:
            initial["groups"] = [default_group.pk]
        return initial


# @admin.register：将管理员账户的管理配置注册到后台站点
@admin.register(StaffUser)
class StaffUserAdmin(AdminAuditMixin, BaseUserAdmin):
    """
    管理员后台管理：

    - queryset 仅包含 account_type=ADMIN
    - 仅超级管理员可增删改，保障后台安全链路
    - 保存时为普通管理员自动分配默认管理员组
    - 注意：此处只能创建普通管理员，超级管理员（最多10个）必须通过命令行创建：
      python manage.py createsuperuser
    """
    add_form = StaffUserCreationForm
    form = StaffUserChangeForm
    # 管理员不涉及队伍信息，保持表单简洁
    exclude = ()
    fieldsets = BaseUserAdmin.fieldsets
    # add_fieldsets：新增管理员时的字段布局，包含基础信息与权限分配
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "email", "password1", "password2"),
            },
        ),
        (
            "权限",
            {
                "fields": ("groups", "user_permissions"),
            },
        ),
    )
    # 只读字段：继承基础只读字段并附加 is_superuser，避免被修改
    readonly_fields = BaseUserAdmin.readonly_fields + ("display_is_superuser",)
    # 列表展示：额外展示超级管理员标志
    list_display = (
        "display_username",
        "account_id",
        "display_email",
        "nickname",
        "display_active",
        "display_email_verified",
        "display_superuser",
    )
    # 过滤条件：按超管与有效状态筛选
    list_filter = ("is_superuser", "is_active")

    def get_queryset(self, request):
        """仅展示管理员账号，避免与普通用户混合"""
        # request: 当前后台管理员请求
        qs = super().get_queryset(request)
        return qs.filter(account_type=User.AccountType.ADMIN)

    def has_change_permission(self, request, obj=None):
        """
        控制修改权限：仅超级管理员可修改管理员账户
        """
        # request: 当前后台管理员请求
        # obj: 正在编辑的管理员对象
        if not request.user.is_superuser:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        """
        控制删除权限：仅超级管理员可删除管理员账户
        """
        # request: 当前后台管理员请求
        # obj: 正在删除的管理员对象
        if not request.user.is_superuser:
            return False
        return super().has_delete_permission(request, obj)

    def has_add_permission(self, request):
        """
        控制新增权限：仅超级管理员可新增管理员
        """
        # request: 当前后台管理员请求
        return request.user.is_superuser

    def get_fieldsets(self, request, obj: StaffUser | None = None):
        """
        根据是否为编辑态决定字段分组

        - 新增管理员：使用 add_fieldsets，避免重复权限板块
        - 编辑管理员：追加权限板块，若对象为超管仅展示 is_superuser
        """
        if obj is None:
            return self.add_fieldsets
        fieldsets = list(super().get_fieldsets(request, obj))
        permission_fields = ("display_is_superuser", "groups", "user_permissions")
        if obj and obj.is_superuser:
            permission_fields = ("display_is_superuser",)
        fieldsets.append(("权限", {"fields": permission_fields}))
        return tuple(fieldsets)

    def save_model(self, request, obj: StaffUser, form, change):
        """
        保存管理员时的安全控制

        - 非超级管理员直接抛出 ValidationError 阻断操作
        - 固定 account_type=ADMIN 且 is_staff=True，保持后台登录能力
        - 若为普通管理员且未分配分组，则自动分配默认管理员组
        """
        # request: 当前后台管理员请求
        # obj: 正在保存的管理员实例
        # form: 提交的管理表单
        # change: 是否编辑模式
        old_obj = None
        if change and obj.pk:
            try:
                old_obj = obj.__class__.objects.get(pk=obj.pk)
            except obj.__class__.DoesNotExist:
                old_obj = None
        if not request.user.is_superuser:
            raise ValidationError("只有超级管理员可以管理管理员账户")
        # 头像上传：若后台上传文件则保存并覆盖头像 URL
        avatar_file = form.cleaned_data.get("avatar_upload") if form else None
        if avatar_file:
            suffix = Path(getattr(avatar_file, "name", "") or "").suffix.lower()
            suffix = suffix if suffix in (".png", ".jpg", ".jpeg", ".webp") else ""
            if not suffix:
                ct_map = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
                suffix = ct_map.get(getattr(avatar_file, "content_type", ""), ".png")
            filename = f"admin_avatar_staff_{getattr(obj, 'pk', 'u')}_{uuid4().hex}{suffix}"
            content = avatar_file.read()
            _, url = default_storage.save_bytes(content=content, filename=filename, subdir="avatars")
            obj.avatar = url or obj.avatar
        obj.account_type = User.AccountType.ADMIN
        obj.is_staff = True
        super().save_model(request, obj, form, change)
        if not obj.is_superuser and not obj.groups.exists():
            assign_default_admin_permissions(obj)
        try:
            obj_refreshed = obj.__class__.objects.get(pk=obj.pk)
        except obj.__class__.DoesNotExist:
            obj_refreshed = obj
        _maybe_force_logout(old_obj, obj_refreshed)

    def get_changeform_initial_data(self, request):
        """预填默认管理员组，减少超管手工勾选"""
        # request: 当前后台管理员请求
        initial = super().get_changeform_initial_data(request)
        default_group = Group.objects.filter(name=DEFAULT_ADMIN_GROUP).first()
        if default_group and "groups" not in initial:
            initial["groups"] = [default_group.pk]
        return initial

    # admin.display：布尔展示是否为超级管理员，列名为“超级管理员”
    @admin.display(boolean=True, description="超级管理员")
    def display_superuser(self, obj: User) -> bool:
        """列表显示是否为超级管理员，方便筛选和审计"""
        return obj.is_superuser

    audit_model = "StaffUser"


# 注意：EmailVerificationCodeAdmin 已迁移至 apps.system.admin
# 邮箱验证码现在在后台的 SYSTEM → 系统日志 - 邮箱验证码 中管理


# 自定义 Group 后台：限制可选权限为业务权限并提供中文标签
try:  # Django 默认已注册 Group，需要先注销再注册
    admin.site.unregister(Group)
except NotRegistered:
    pass


@admin.register(Group)
class GroupAdmin(AdminAuditMixin, admin.ModelAdmin):
    """
    权限组管理：仅展示业务权限，使用中文标签便于运营选择

    - 权限字段过滤为 PERMISSION_ITEMS（排除 Django 内置模型权限）
    - label_from_instance 转换为中文描述，缺少定义时按“模型-动作”回退
    """

    search_fields = ("name",)
    filter_horizontal = ("permissions",)
    audit_model = "Group"

    def formfield_for_manytomany(self, db_field, request=None, **kwargs):
        """限制权限选择范围并输出中文标签"""
        field = super().formfield_for_manytomany(db_field, request=request, **kwargs)
        if field and db_field.name == "permissions":
            field.queryset = _filter_biz_permissions(field.queryset)
            field.label_from_instance = _label_biz_permission
            field.label = "权限列表"
        return field
