from __future__ import annotations

import json
from datetime import datetime
from django.contrib import admin
from django import forms
from django.core.exceptions import ValidationError
from django.http import HttpResponse, HttpRequest
from django.urls import path, reverse
from django.utils.html import format_html

from apps.common.infra.logger import get_logger, logger_extra
from apps.common.utils.validators import validate_image_file
from apps.common.exceptions import ValidationError as BizValidationError
from .services import ConfigService
from .models import (
    SystemConfig,
    MailAccount,
    SystemLogCategory,
    SystemLog,
    EmailVerificationCode,
    AdminActionLog,
)

logger = get_logger(__name__)
config_service = ConfigService()


class AdminAuditMixin:
    """
    后台审计日志混入类：记录增删改关键对象

    功能：
    - 在管理员对模型进行增删改操作时自动记录审计日志
    - 同时记录到文件日志（logger）和数据库（AdminActionLog）
    - 记录操作者、模型类型、对象ID、操作类型、IP、User-Agent等信息
    - 记录字段变更的前后对比（JSON格式）
    - 便于追溯敏感操作的责任人与时间点

    使用方法：
    - 在 ModelAdmin 中继承此混入类
    - 可选：设置 audit_model 属性指定模型名称（默认使用对象类名）
    """

    audit_model = ""

    @staticmethod
    def _get_client_ip(request):
        """
        获取客户端真实 IP 地址

        考虑代理情况，优先从 X-Forwarded-For 读取
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # 多级代理时取第一个IP
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    @staticmethod
    def _get_field_changes(request, obj, form=None):
        """
        获取字段变更详情

        对比修改前后的字段值，构造 changes 字典
        格式：{"field_name": {"old": "旧值", "new": "新值"}}
        """
        _ = request
        _ = obj
        if form is None or not hasattr(form, 'changed_data'):
            return None

        changes = {}
        for field_name in form.changed_data:
            # 跳过敏感字段（密码等）
            if 'password' in field_name.lower():
                changes[field_name] = {"old": "******", "new": "******"}
                continue

            try:
                # 获取初始值（修改前）
                old_value = form.initial.get(field_name, None)
                # 获取新值（修改后）
                new_value = form.cleaned_data.get(field_name, None)

                # 转换为可序列化的格式
                if old_value != new_value:
                    changes[field_name] = {
                        "old": str(old_value) if old_value is not None else None,
                        "new": str(new_value) if new_value is not None else None,
                    }
            except Exception as e:  # noqa: BLE001
                # 跳过无法序列化的字段
                logger.warning(f"无法记录字段 {field_name} 的变更: {e}")
                continue

        return changes if changes else None

    def _save_audit_log(self, request, obj, action_type, message="", changes=None):
        """
        保存审计日志到 AdminActionLog 模型

        参数：
        - request: Django 请求对象
        - obj: 被操作的对象
        - action_type: 操作类型（create/update/delete）
        - message: 操作说明
        - changes: 变更详情（字典）
        """
        try:
            AdminActionLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                username=getattr(request.user, 'username', 'anonymous'),
                action_type=action_type,
                content_type=self.audit_model or obj.__class__.__name__,
                object_id=str(getattr(obj, 'pk', '')) if obj else '',
                object_repr=str(obj) if obj else '',
                changes=changes,
                message=message,
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:255],
            )
        except Exception as e:  # noqa: BLE001
            # 记录失败不应阻塞主流程，仅记录错误日志
            logger.error(f"保存审计日志失败: {e}", extra=logger_extra({
                "admin": getattr(request.user, 'username', None),
                "model": self.audit_model or (obj.__class__.__name__ if obj else 'Unknown'),
                "action": action_type,
            }))

    def log_change(self, request, obj, message):
        """
        修改操作审计：记录管理员修改对象的操作

        同时记录到文件日志和数据库
        """
        super().log_change(request, obj, message)  # type: ignore[misc]

        # 文件日志
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

        # 数据库审计日志
        # 注意：此处 message 是 Django 的 LogEntry message（list格式），需要提取可读文本
        message_text = str(message[0]['changed']['fields']) if isinstance(message, list) and message else str(message)
        self._save_audit_log(
            request=request,
            obj=obj,
            action_type=AdminActionLog.ActionType.UPDATE,
            message=f"修改对象: {message_text}",
            changes=None,  # Django Admin 的 message 已包含变更信息
        )

    def log_addition(self, request, obj, message):
        """
        新增操作审计：记录管理员创建对象的操作

        同时记录到文件日志和数据库
        """
        super().log_addition(request, obj, message)  # type: ignore[misc]

        # 文件日志
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

        # 数据库审计日志
        self._save_audit_log(
            request=request,
            obj=obj,
            action_type=AdminActionLog.ActionType.CREATE,
            message=f"创建对象: {str(obj)}",
        )

    def log_deletion(self, request, obj, object_repr):
        """
        删除操作审计：记录管理员删除对象的操作

        同时记录到文件日志和数据库
        """
        super().log_deletion(request, obj, object_repr)  # type: ignore[misc]

        # 文件日志
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

        # 数据库审计日志
        self._save_audit_log(
            request=request,
            obj=obj,
            action_type=AdminActionLog.ActionType.DELETE,
            message=f"删除对象: {object_repr}",
        )

    def save_model(self, request, obj, form, change):
        """
        保存模型时记录字段变更

        在父类保存前捕获字段变更，便于精确记录修改内容
        """
        # 如果是修改操作，捕获字段变更
        if change:
            changes = self._get_field_changes(request, obj, form)
            # 暂存到请求对象，供 log_change 使用
            request._audit_changes = changes

        # 调用父类保存逻辑
        super().save_model(request, obj, form, change)  # type: ignore[misc]


@admin.register(SystemConfig)
class SystemConfigAdmin(AdminAuditMixin, admin.ModelAdmin):
    """
    系统配置后台管理：
    - 支持在运行期为配置键设定覆盖值
    - 核心键需谨慎操作，建议超级管理员管理
    - 自动记录所有配置修改操作到审计日志
    """

    audit_model = "SystemConfig"

    list_display = ("key", "description", "value_type", "current_value", "is_required", "is_sensitive", "updated_at")
    list_filter = ("value_type", "is_required", "is_sensitive")
    search_fields = ("key", "description")
    ordering = ("key",)
    readonly_fields = ("key", "description", "detail_description", "value_type", "is_sensitive", "is_required")

    class SystemConfigAdminForm(forms.ModelForm):
        """根据值类型切换表单控件并做类型校验"""

        class Meta:
            model = SystemConfig
            fields = (
                "key",
                "value",
                "value_type",
                "is_sensitive",
                "is_required",
                "description",
                "detail_description",
            )

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            cfg = self.instance

            # 根据值类型切换表单控件
            if cfg.value_type == SystemConfig.ValueType.INT:
                self.fields["value"] = forms.IntegerField(
                    label="配置值",
                    required=cfg.is_required,
                    initial=cfg.cast_value(),
                    help_text="",
                )
            elif cfg.value_type == SystemConfig.ValueType.BOOL:
                # 布尔类型：使用下拉框而不是勾选框，避免状态不匹配
                # 确定当前值：优先使用数据库值，否则从 settings.py 读取
                if cfg.value and cfg.value.strip():
                    # 数据库已有值，使用 cast_value() 解析
                    initial_value = cfg.cast_value()
                else:
                    # 数据库无值，从 settings.py 读取默认布尔值
                    from django.conf import settings
                    initial_value = getattr(settings, cfg.key, False)

                self.fields["value"] = forms.ChoiceField(
                    label="配置值",
                    required=True,
                    choices=[
                        ("True", "True"),
                        ("False", "False"),
                    ],
                    initial="True" if initial_value else "False",
                    help_text="",
                )
            elif cfg.value_type == SystemConfig.ValueType.JSON:
                self.fields["value"] = forms.JSONField(
                    label="配置值",
                    required=cfg.is_required,
                    initial=cfg.cast_value(),
                    help_text="",
                )
            else:
                widget = forms.PasswordInput(render_value=True) if cfg.is_sensitive else forms.TextInput()
                self.fields["value"] = forms.CharField(
                    label="配置值",
                    required=cfg.is_required,
                    initial=cfg.cast_value(),
                    widget=widget,
                    help_text="",
                )

            # 只读字段保持禁用，防止误改元信息
            for name in (
                    "key",
                    "value_type",
                    "is_sensitive",
                    "is_required",
                    "description",
                    "detail_description",
            ):
                if name in self.fields and name != "value":
                    self.fields[name].disabled = True

        def clean_value(self):
            """按类型校验并转为字符串存储"""
            cfg = self.instance
            val = self.cleaned_data.get("value")

            if cfg.value_type == SystemConfig.ValueType.INT and not isinstance(val, int):
                raise forms.ValidationError("请输入整数")
            if cfg.value_type == SystemConfig.ValueType.BOOL:
                # 布尔类型现在使用 ChoiceField，val 已经是 "True" 或 "False" 字符串
                # 校验值必须是这两者之一
                if val not in ("True", "False"):
                    raise forms.ValidationError("布尔值必须是 True 或 False")
                # 直接返回字符串，不需要转换
            if cfg.value_type == SystemConfig.ValueType.JSON and val is None and cfg.is_required:
                raise forms.ValidationError("必填项不能为空")
            if cfg.is_required and val in (None, ""):
                raise forms.ValidationError("必填项不能为空")
            return val

        def save(self, commit=True):
            cfg = super().save(commit=False)
            val = self.cleaned_data.get("value")
            # 持久化为字符串
            if cfg.value_type == SystemConfig.ValueType.JSON:
                cfg.value = self.fields["value"].widget.value_from_datadict(
                    {"value": val}, {}, "value"
                )
            else:
                cfg.value = str(val) if val is not None else ""
            if commit:
                cfg.save()
            return cfg

    form = SystemConfigAdminForm

    def save_model(self, request, obj: SystemConfig, form, change):
        """保存时记录日志，提示仅覆盖运行期配置"""
        super().save_model(request, obj, form, change)
        config_service.invalidate(obj.key)
        logger.info(
            "更新系统配置",
            extra=logger_extra(
                {"admin": getattr(request.user, "username", None), "key": obj.key}
            ),
        )

    @admin.display(description="值预览")
    def current_value(self, obj: SystemConfig) -> str:
        """
        当前生效值：
        - 若后台启用则取配置值
        - 否则回退到 settings/.env
        - 敏感字段脱敏
        """
        effective = config_service.get(obj.key, "")
        if obj.is_sensitive and effective not in (None, ""):
            return "******"
        return "" if effective is None else str(effective)

    def has_add_permission(self, request):
        """禁止新增，统一由预置配置生成"""
        _ = request
        return False

    def has_delete_permission(self, request, obj=None):
        """禁止删除配置项"""
        _ = request
        _ = obj
        return False

    def get_queryset(self, request):
        """进入后台前确保预置配置存在"""
        config_service.ensure_supported_configs()
        qs = super().get_queryset(request)
        return qs.filter(key__in=config_service.SUPPORTED_CONFIGS.keys())


@admin.register(MailAccount)
class MailAccountAdmin(AdminAuditMixin, admin.ModelAdmin):
    """
    邮件账号后台管理：用于管理发送邮箱及其优先级

    业务场景：
    - 统一管理平台的 SMTP 发信账号
    - 支持多个邮箱账号并通过优先级控制使用顺序
    - 可设置默认发信账号

    功能：
    - 列表展示基础配置与启用状态
    - 支持按提供商/启用/默认过滤
    - 排序按 priority，优先级越小越靠前
    - 自动审计增删改操作
    """

    # 列表展示字段：基础 SMTP 配置信息与启用状态/优先级
    list_display = (
        "name",
        "provider",
        "username",
        "host",
        "port",
        "is_active",
        "is_default",
        "priority",
    )
    # 过滤条件：按提供商/启用状态/默认标志筛选
    list_filter = ("provider", "is_active", "is_default")
    # 搜索字段：支持按名称/用户名/主机搜索
    search_fields = ("name", "username", "host")
    # 排序规则：按优先级升序排列，优先级越小越靠前
    ordering = ("priority",)
    # 审计模型名称标识
    audit_model = "MailAccount"

    class MailAccountAdminForm(forms.ModelForm):
        """
        邮件账号自定义表单：host 必填校验

        功能：
        - 确保 SMTP 主机不能为空
        - 防止管理员创建无效的发信账号配置
        """

        connection_security = forms.ChoiceField(
            label="连接加密方式",
            choices=(
                ("tls", "TLS"),
                ("ssl", "SSL"),
                ("none", "不加密"),
            ),
            initial="tls",
            required=False,
            help_text="TLS/SSL 二选一，默认 TLS；不加密仅限可信网络",
        )

        class Meta:
            model = MailAccount
            fields = "__all__"

        def __init__(self, *args, **kwargs):
            """初始化表单时标记 host 为必填"""
            super().__init__(*args, **kwargs)
            if "host" in self.fields:
                self.fields["host"].required = True
            # 发信邮箱固定等于用户名，隐藏 from_email 字段避免误填
            if "from_email" in self.fields:
                self.fields["from_email"].widget = forms.HiddenInput()
            # 隐藏底层 TLS/SSL 字段，改用下拉控制
            for name in ("use_tls", "use_ssl"):
                if name in self.fields:
                    self.fields[name].widget = forms.HiddenInput()
            # 设置下拉初始值
            initial_security = "tls"
            obj = kwargs.get("instance")
            if obj:
                if getattr(obj, "use_ssl", False):
                    initial_security = "ssl"
                elif not getattr(obj, "use_tls", False):
                    initial_security = "none"
            self.fields["connection_security"].initial = initial_security

        def clean(self):
            """校验 SMTP 主机不能为空"""
            cleaned = super().clean()
            if not cleaned.get("host"):
                raise ValidationError("SMTP 主机不能为空，请手动填写")
            # 根据下拉设置 TLS/SSL
            sec = cleaned.get("connection_security") or "tls"
            cleaned["use_tls"] = sec == "tls"
            cleaned["use_ssl"] = sec == "ssl"
            # 校验验证码有效期区间
            expire_minutes = cleaned.get("verification_expire_minutes") or 10
            try:
                expire_minutes = int(expire_minutes)
            except (TypeError, ValueError):
                raise ValidationError("验证码有效时间需为正整数")
            if expire_minutes < 5 or expire_minutes > 30:
                raise ValidationError("验证码有效时间需在 5-30 分钟之间")
            cleaned["verification_expire_minutes"] = expire_minutes
            # 校验 Logo 图片类型/大小
            logo_file = cleaned.get("logo")
            if logo_file:
                try:
                    validate_image_file(logo_file, max_size_mb=2)
                except BizValidationError as exc:
                    raise ValidationError(exc.message)
            return cleaned

    form = MailAccountAdminForm
    fieldsets = (
        (
            "基础信息",
            {
                "fields": (
                    "name",
                    "provider",
                    "username",
                    "password",
                )
            },
        ),
        (
            "服务器配置",
            {
                "fields": (
                    "host",
                    "port",
                    "connection_security",
                )
            },
        ),
        (
            "展示与内容",
            {
                "fields": (
                    "from_name",
                    "support_email",
                    "site_url",
                    "logo",
                    "logo_preview",
                    "verification_subject",
                    "verification_expire_minutes",
                    "priority",
                    "is_default",
                    "is_active",
                )
            },
        ),
    )

    def get_form(self, request, obj=None, **kwargs):
        """
        获取表单时添加详细的帮助文本

        功能：
        - 为每个字段提供中文说明和配置示例
        - 降低管理员配置 SMTP 的理解成本
        - 避免误配发信参数导致邮件发送失败
        """
        kwargs.setdefault("form", self.form)
        form = super().get_form(request, obj, **kwargs)
        help_texts = {
            "name": "发信账号的显示名称，便于后台识别",
            "provider": "邮件服务提供商类型（如 SMTP、企业邮箱等）",
            "username": "发信账号用户名，同时作为发信邮箱（MAIL FROM），必须填写完整邮箱地址",
            "password": "发信授权码或密码，注意保密",
            "host": "SMTP 服务器地址（示例：QQ smtp.qq.com，163 smtp.163.com，Gmail smtp.gmail.com，Outlook smtp.office365.com）",
            "port": "SMTP 服务器端口，通常 465(SSL) / 587(TLS)",
            "connection_security": "连接加密方式，TLS/SSL 二选一，默认 TLS",
            "is_active": "关闭后不会参与发信",
            "is_default": "标记默认发信账号，优先使用",
            "priority": "数字越小优先级越高，同一场景按优先级选择账号",
            "from_name": "邮件中的发信名称（From）；留空则只显示用户名邮箱",
            "verification_subject": "邮件的主题，留空默认使用“您的验证码”",
            "verification_expire_minutes": "验证码有效时间（分钟），默认 10 分钟",
            "support_email": "支持/联系邮箱，留空默认等于用户名，用于邮件页脚",
            "site_url": "可选站点链接，填入后邮件页脚展示",
            "logo": "可选邮件 Logo，上传图片后显示在邮件顶部",
        }
        for name, text in help_texts.items():
            if name in form.base_fields:
                form.base_fields[name].help_text = text
        return form

    readonly_fields = ("logo_preview",)

    @admin.display(description="Logo 预览")
    def logo_preview(self, obj):
        """后台展示已上传的 Logo，便于管理员确认图片"""
        if obj and getattr(obj, "logo", None):
            try:
                return format_html('<img src="{}" style="max-height: 120px; max-width: 240px;" alt="Logo预览" />',
                                   obj.logo.url)
            except Exception:
                return "Logo 无法预览"
        return "未上传 Logo"


# ===========================
# 自定义过滤器（用于 SystemLogAdmin）
# ===========================


class LevelFilter(admin.SimpleListFilter):
    """日志级别过滤器"""
    title = "日志级别"
    parameter_name = "level"

    def lookups(self, request, model_admin):
        """返回过滤选项：INFO, WARNING, ERROR, CRITICAL"""
        _ = request
        _ = model_admin
        return (
            ("INFO", "INFO"),
            ("WARNING", "WARNING"),
            ("ERROR", "ERROR"),
            ("CRITICAL", "CRITICAL"),
        )

    def queryset(self, request, queryset):
        """过滤逻辑由 get_queryset() 统一处理"""
        _ = request
        return queryset


class TypeFilter(admin.SimpleListFilter):
    """日志类型过滤器"""
    title = "日志类型"
    parameter_name = "log_type"

    def lookups(self, request, model_admin):
        """返回过滤选项：业务日志、框架日志、系统日志、其他"""
        _ = request
        _ = model_admin
        return (
            ("business", "业务日志"),
            ("framework", "框架日志"),
            ("system", "系统日志"),
            ("other", "其他"),
        )

    def queryset(self, request, queryset):
        """过滤逻辑由 get_queryset() 统一处理"""
        _ = request
        return queryset


class SourceFilter(admin.SimpleListFilter):
    """日志来源过滤器（基于logger_name提取模块）"""
    title = "日志来源"
    parameter_name = "log_source"

    def lookups(self, request, model_admin):
        """动态返回所有可用的日志来源（从日志中提取）"""
        # 注意：这里只提供常见模块，实际过滤在 get_queryset() 中处理
        _ = request
        _ = model_admin
        return (
            ("accounts", "accounts"),
            ("contests", "contests"),
            ("challenges", "challenges"),
            ("submissions", "submissions"),
            ("machines", "machines"),
            ("system", "system"),
            ("django", "django"),
        )

    def queryset(self, request, queryset):
        """过滤逻辑由 get_queryset() 统一处理"""
        _ = request
        return queryset


class AccountTypeFilter(admin.SimpleListFilter):
    """账户类型过滤器（基于account_id范围）"""
    title = "账户类型"
    parameter_name = "account_type"

    def lookups(self, request, model_admin):
        """返回过滤选项：超管、管理员、普通用户、未登录"""
        _ = request
        _ = model_admin
        return (
            ("superuser", "超级管理员 (ID 1-10)"),
            ("staff", "管理员 (ID 11-1000)"),
            ("user", "普通用户 (ID 1001+)"),
            ("anonymous", "未登录用户"),
        )

    def queryset(self, request, queryset):
        """过滤逻辑由 get_queryset() 统一处理"""
        _ = request
        return queryset


@admin.register(SystemLog)
class SystemLogAdmin(admin.ModelAdmin):
    """
    系统日志后台管理：用于查看和导出系统日志（基于FTC日志标准）

    功能：
    - 从日志文件读取日志条目并在后台展示
    - 使用LogParser解析PLAIN/JSON格式日志
    - 显示9个字段：ID、时间、级别、类型、来源、消息摘要、账户名、账户ID、IP
    - 支持4种过滤器：级别、类型、来源、账户类型
    - 提供日志文件导出功能
    - 只读模式，不允许增删改

    符合标准：docs/日志标准.md
    """

    change_list_template = "admin/system/systemlog/change_list.html"
    change_form_template = "admin/system/systemlog/change_form.html"
    default_limit = 500
    limit_step = 500
    max_limit = 5000

    # 列表展示字段（9个字段）
    list_display = (
        "row_id",
        "timestamp",
        "level",
        "log_type",
        "log_source",
        "message_summary",
        "username",
        "account_id",
        "ip_address",
    )
    # 过滤条件（4个自定义过滤器）
    list_filter = (LevelFilter, TypeFilter, SourceFilter, AccountTypeFilter)
    # 搜索字段
    search_fields = ("message", "username", "ip_address")
    # 排序：默认按时间倒序显示最新日志
    ordering = ("-timestamp",)
    # 每页显示数量
    list_per_page = 100

    # 详情页字段配置（统一一行一个字段）
    fields = (
        "id",
        "timestamp",
        "level",
        "log_type_display",
        "log_source_display",
        "message",
        "username_display",
        "account_id_display",
        "ip_address_display",
        "request_path_display",
    )

    # 只读字段（详情页显示所有字段为只读）
    readonly_fields = (
        "id",
        "timestamp",
        "level",
        "log_type_display",
        "log_source_display",
        "message",
        "username_display",
        "account_id_display",
        "ip_address_display",
        "request_path_display",
    )

    # 禁用所有写操作，但允许查看详情
    def has_add_permission(self, request: HttpRequest) -> bool:
        """禁止添加日志"""
        return False

    def has_change_permission(self, request: HttpRequest, obj=None) -> bool:
        """禁止修改日志（但允许查看）"""
        return False

    def has_delete_permission(self, request: HttpRequest, obj=None) -> bool:
        """禁止删除日志"""
        return False

    @admin.display(description="序号")
    def row_id(self, obj) -> int:
        """返回日志序号（按倒序列表位置）"""
        return getattr(obj, "row_id", obj.id)

    @admin.display(description="时间戳")
    def timestamp(self, obj) -> str:
        """返回时间戳"""
        return obj.timestamp

    @admin.display(description="级别")
    def level(self, obj) -> str:
        """返回日志级别"""
        return obj.level

    @admin.display(description="类型")
    def log_type(self, obj) -> str:
        """返回日志类型：业务日志/框架日志/系统日志/其他"""
        return obj.get_type()

    @admin.display(description="来源")
    def log_source(self, obj) -> str:
        """返回日志来源（模块名）"""
        return obj.get_source()

    @admin.display(description="消息摘要")
    def message_summary(self, obj) -> str:
        """返回消息摘要（智能截断）"""
        return obj.get_summary(max_length=100)

    @admin.display(description="账户名")
    def username(self, obj) -> str:
        """返回账户名"""
        return obj.username or "-"

    @admin.display(description="账户ID")
    def account_id(self, obj) -> str:
        """返回账户ID"""
        return str(obj.account_id) if obj.account_id is not None else "-"

    @admin.display(description="IP地址")
    def ip_address(self, obj) -> str:
        """返回IP地址"""
        return obj.ip_address or "-"

    # 详情页专用display方法
    @admin.display(description="日志类型")
    def log_type_display(self, obj) -> str:
        """详情页显示日志类型"""
        return obj.get_type()

    @admin.display(description="日志来源")
    def log_source_display(self, obj) -> str:
        """详情页显示日志来源"""
        return obj.get_source()

    @admin.display(description="账户名")
    def username_display(self, obj) -> str:
        """详情页显示账户名"""
        return obj.username or "-"

    @admin.display(description="账户ID")
    def account_id_display(self, obj) -> str:
        """详情页显示账户ID"""
        return str(obj.account_id) if obj.account_id is not None else "-"

    @admin.display(description="IP地址")
    def ip_address_display(self, obj) -> str:
        """详情页显示IP地址"""
        return obj.ip_address or "-"

    @admin.display(description="请求路径")
    def request_path_display(self, obj) -> str:
        """详情页显示请求路径"""
        return obj.request_path or "-"

    def _resolve_limit(self, request: HttpRequest) -> int:
        """根据请求参数解析展示的日志条数"""
        try:
            limit = int(request.GET.get("limit", self.default_limit))
        except (TypeError, ValueError):
            limit = self.default_limit
        limit = max(self.limit_step, min(limit, self.max_limit))
        return limit

    def get_queryset(self, request: HttpRequest):
        """
        重写 queryset：从日志文件读取数据并应用过滤条件

        使用 LogParser 解析日志文件，支持 PLAIN 和 JSON 两种格式
        支持4种过滤器：级别、类型、来源、账户类型
        """
        from apps.system.log_models import LogParser
        from apps.common.infra.logger import get_log_path_from_config
        from pathlib import Path

        logs = []
        limit = self._resolve_limit(request)
        request._systemlog_limit = limit
        # 预取 limit+1 条，用于判断是否还有更多日志可加载
        has_more = False

        try:
            # 从配置获取日志文件路径
            log_file_path = get_log_path_from_config()

            if not Path(log_file_path).exists():
                logger.warning(f"日志文件不存在: {log_file_path}")
            else:
                # 使用 LogParser 解析日志
                parser = LogParser(log_file_path)

                # 读取最新 limit+1 条日志（默认倒序返回），多取一条判断是否还有更多
                log_entries = list(parser.parse_file(limit=limit + 1, order="desc"))
                if len(log_entries) > limit:
                    has_more = True
                    log_entries = log_entries[:limit]

                # 直接使用 LogEntry 对象，并记录序号
                for idx, entry in enumerate(log_entries, start=1):
                    # noinspection PyProtectedMember
                    entry._state.adding = False  # type: ignore[attr-defined, protected-access]
                    entry.row_id = idx
                    logs.append(entry)

        except Exception as e:  # noqa: BLE001
            logger.error(f"读取日志文件失败: {e}")

        # ===========================
        # 应用过滤条件
        # ===========================
        def _get_filter_value(name: str):
            """
            兼容 Django Admin 可能使用 name 或 name__exact 作为查询参数的情况
            """
            return request.GET.get(name) or request.GET.get(f"{name}__exact")

        # 1. 级别过滤（LevelFilter）
        level_filter = _get_filter_value("level")
        if level_filter:
            logs = [log for log in logs if log.level == level_filter]

        # 2. 类型过滤（TypeFilter）
        type_filter = _get_filter_value("log_type")
        if type_filter:
            type_map = {
                "business": "业务日志",
                "framework": "框架日志",
                "system": "系统日志",
                "other": "其他",
            }
            target_type = type_map.get(type_filter)
            if target_type:
                logs = [log for log in logs if log.get_type() == target_type]

        # 3. 来源过滤（SourceFilter）
        source_filter = _get_filter_value("log_source")
        if source_filter:
            logs = [log for log in logs if source_filter in log.get_source()]

        # 4. 账户类型过滤（AccountTypeFilter）
        account_type_filter = _get_filter_value("account_type")
        if account_type_filter:
            filtered_logs = []
            for log in logs:
                account_id = log.account_id

                if account_type_filter == "anonymous":
                    # 未登录用户：account_id 为 None 或 "-"
                    if account_id is None or account_id == "-":
                        filtered_logs.append(log)

                elif account_type_filter == "superuser":
                    # 超级管理员：account_id 1-10
                    if account_id and str(account_id).isdigit() and 1 <= int(account_id) <= 10:
                        filtered_logs.append(log)

                elif account_type_filter == "staff":
                    # 管理员：account_id 11-1000
                    if account_id and str(account_id).isdigit() and 11 <= int(account_id) <= 1000:
                        filtered_logs.append(log)

                elif account_type_filter == "user":
                    # 普通用户：account_id 1001+
                    if account_id and str(account_id).isdigit() and int(account_id) >= 1001:
                        filtered_logs.append(log)

            logs = filtered_logs

        # 返回伪造的 QuerySet
        class FakeQuery:
            """伪造的 Query 对象"""
            select_related = False
            order_by = []

        class FakeQuerySet(list):
            """伪造的 QuerySet，用于在 Admin 中显示非数据库数据"""

            def __init__(self, data):
                super().__init__(data)
                self.model = SystemLog
                self.ordered = True
                self._result_cache = data
                self.query = FakeQuery()

            def count(self, *args, **kwargs):  # type: ignore[override]
                _ = args
                _ = kwargs
                return len(self)

            def order_by(self, *args, **kwargs):  # type: ignore[override]
                _ = args
                _ = kwargs
                return self

            def filter(self, *args, **kwargs):  # type: ignore[override]
                _ = args
                _ = kwargs
                return self

            def exclude(self, *args, **kwargs):  # type: ignore[override]
                _ = args
                _ = kwargs
                return self

            def all(self):
                return self

            def distinct(self, *args, **kwargs):  # type: ignore[override]
                _ = args
                _ = kwargs
                return self

            def values_list(self, *fields, **kwargs):  # type: ignore[override]
                flat = kwargs.get('flat', False)
                if not fields:
                    return []
                field_name = fields[0]
                values = []
                for obj in self:
                    value = getattr(obj, field_name, None)
                    if value and value not in values:
                        values.append(value)
                if flat:
                    return values
                return [(v,) for v in values]

            def values(self, *fields):  # type: ignore[override]
                result = []
                for obj in self:
                    item = {}
                    for field in fields:
                        item[field] = getattr(obj, field, None)
                    result.append(item)
                return result

            def exists(self):
                return len(self) > 0

            @staticmethod
            def none():
                return FakeQuerySet([])

            def using(self, alias):
                _ = alias
                return self

            def select_related(self, *args):
                _ = args
                return self

            def prefetch_related(self, *args):
                _ = args
                return self

            def _clone(self):  # type: ignore[override]
                """克隆QuerySet（Django Admin内部使用）"""
                return FakeQuerySet(list(self))

            def get(self, **kwargs):
                """
                模拟QuerySet.get()方法

                根据条件查找单个日志对象
                通常用于通过pk或id查找
                """
                # 允许访问已不在当前分页的 ID：通过日志文件重新解析定位
                from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
                from apps.common.infra.logger import get_log_path_from_config
                from apps.system.log_models import LogParser
                from pathlib import Path

                # 先在当前缓冲中查找
                matches = []
                for obj in self:
                    match = True
                    for key, value in kwargs.items():
                        if key == 'pk':
                            key = 'id'
                        obj_value = getattr(obj, key, None)
                        if obj_value != value:
                            match = False
                            break
                    if match:
                        matches.append(obj)

                if len(matches) == 1:
                    return matches[0]
                if len(matches) > 1:
                    raise MultipleObjectsReturned(f"找到多个匹配的日志对象: {kwargs}")

                # 缓冲未命中：尝试直接从日志文件解析对应行号
                pk = kwargs.get("id") or kwargs.get("pk")
                if pk is None:
                    raise ObjectDoesNotExist(f"日志对象不存在: {kwargs}")
                try:
                    pk_int = int(pk)
                except (TypeError, ValueError):
                    raise ObjectDoesNotExist(f"日志对象不存在: {kwargs}")

                # noinspection PyBroadException
                try:
                    log_path = get_log_path_from_config()
                    if Path(log_path).exists():
                        log_parser = LogParser(log_path)
                        for log_entry in log_parser.parse_file(limit=None, order="asc"):
                            if log_entry.id == pk_int:
                                # noinspection PyProtectedMember
                                log_entry._state.adding = False  # type: ignore[attr-defined, protected-access]
                                log_entry.row_id = pk_int
                                return log_entry
                except Exception as exc:  # noqa: BLE001
                    logger.debug("解析日志文件时定位日志失败", extra={"error": str(exc)})

                raise ObjectDoesNotExist(f"日志对象不存在: {kwargs}")

        request._systemlog_count = len(logs)
        request._systemlog_has_more = has_more
        return FakeQuerySet(logs)

    def changelist_view(self, request, extra_context=None):
        """
        重写changelist视图：添加导出链接与“加载更多”入口
        """
        extra_context = extra_context or {}
        current_limit = self._resolve_limit(request)
        next_limit = min(current_limit + self.limit_step, self.max_limit)
        # 显示区块：只要未到最大上限，或已加载超过默认条数（便于显示“恢复默认”按钮）就展示
        show_more = (current_limit < self.max_limit) or (current_limit > self.default_limit)
        # 是否还能继续加载更多
        can_load_more = current_limit < self.max_limit
        extra_context["export_urls"] = {
            "txt": reverse("admin:system_systemlog_export_txt"),
            "csv": reverse("admin:system_systemlog_export_csv"),
            "json": reverse("admin:system_systemlog_export_json"),
        }
        extra_context["show_load_more"] = show_more
        extra_context["log_limit"] = current_limit
        extra_context["next_limit"] = next_limit
        extra_context["can_load_more"] = can_load_more
        extra_context["default_limit"] = self.default_limit
        extra_context["next_limit_url"] = self._build_limit_url(request, next_limit)
        extra_context["default_limit_url"] = self._build_limit_url(request, self.default_limit)
        return super().changelist_view(request, extra_context=extra_context)

    def _build_limit_url(self, request: HttpRequest, limit: int) -> str:
        _ = self
        params = request.GET.copy()
        params["limit"] = limit
        query = params.urlencode()
        return f"{request.path}?{query}" if query else f"{request.path}?limit={limit}"

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        """在详情页注入单条导出链接"""
        extra_context = extra_context or {}
        if object_id:
            extra_context["single_export_urls"] = {
                fmt: reverse("admin:system_systemlog_export_single", args=[object_id, fmt])
                for fmt in ("txt", "csv", "json")
            }
        return super().changeform_view(request, object_id, form_url, extra_context)

    @staticmethod
    def _find_log_entry_by_id(log_file_path: str, log_id: int):
        """遍历日志文件找到对应ID的条目"""
        from apps.system.log_models import LogParser

        parser = LogParser(log_file_path)
        for entry in parser.parse_file(limit=None, order="asc"):
            if entry.id == log_id:
                return entry
        return None

    def get_urls(self):
        """添加自定义 URL：日志导出（支持3种格式：TXT/CSV/JSON）"""
        urls = super().get_urls()
        custom_urls = [
            path("export/txt/", self.admin_site.admin_view(self.export_logs_txt), name="system_systemlog_export_txt"),
            path("export/csv/", self.admin_site.admin_view(self.export_logs_csv), name="system_systemlog_export_csv"),
            path("export/json/", self.admin_site.admin_view(self.export_logs_json),
                 name="system_systemlog_export_json"),
            path("<path:object_id>/export/<str:fmt>/", self.admin_site.admin_view(self.export_single_log),
                 name="system_systemlog_export_single"),
        ]
        return custom_urls + urls

    @staticmethod
    def export_logs_txt(request: HttpRequest) -> HttpResponse:
        """
        导出日志文件 - TXT格式（原始日志文件）

        功能：
        - 直接下载完整的日志文件（PLAIN格式）
        - 文件名包含导出时间戳

        说明：后台场景下直接使用 HttpResponse 返回文件下载，
        不走统一 API 封装，避免影响附件下载体验。
        """
        from apps.common.infra.logger import get_log_path_from_config
        from pathlib import Path
        _ = request

        log_file_path = get_log_path_from_config()

        if not Path(log_file_path).exists():
            return HttpResponse("日志文件不存在", status=404)

        try:
            with open(log_file_path, "rb") as f:
                response = HttpResponse(f.read(), content_type="text/plain; charset=utf-8")
                filename = f"system_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
                response["Content-Disposition"] = f'attachment; filename="{filename}"'
                return response
        except Exception as e:  # noqa: BLE001
            logger.error(f"导出日志文件失败(TXT): {e}")
            return HttpResponse(f"导出失败: {str(e)}", status=500)

    @staticmethod
    def export_logs_csv(request: HttpRequest) -> HttpResponse:
        """
        导出日志文件 - CSV格式

        功能：
        - 将日志解析为CSV表格
        - 包含9个字段：ID、时间、级别、类型、来源、消息、账户名、账户ID、IP

        说明：后台下载场景直接返回 HttpResponse。
        """
        import csv
        import io
        from apps.system.log_models import LogParser
        from apps.common.infra.logger import get_log_path_from_config
        from pathlib import Path
        _ = request

        log_file_path = get_log_path_from_config()

        if not Path(log_file_path).exists():
            return HttpResponse("日志文件不存在", status=404)

        try:
            # 解析日志
            parser = LogParser(log_file_path)
            log_entries = list(parser.parse_file(limit=10000))  # 最多导出10000条
            log_entries.reverse()  # 最新的在前

            # 创建CSV
            output = io.StringIO()
            writer = csv.writer(output)

            # 写入表头
            writer.writerow([
                "ID", "时间戳", "级别", "类型", "来源", "消息", "账户名", "账户ID", "IP地址"
            ])

            # 写入数据
            for idx, entry in enumerate(log_entries, start=1):
                writer.writerow([
                    idx,
                    entry.timestamp,
                    entry.level,
                    entry.get_type(),
                    entry.get_source(),
                    entry.message,
                    entry.username or "-",
                    entry.account_id or "-",
                    entry.ip_address or "-",
                ])

            # 返回响应
            response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8-sig")
            filename = f"system_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response

        except Exception as e:  # noqa: BLE001
            logger.error(f"导出日志文件失败(CSV): {e}")
            return HttpResponse(f"导出失败: {str(e)}", status=500)

    @staticmethod
    def export_logs_json(request: HttpRequest) -> HttpResponse:
        """
        导出日志文件 - JSON格式

        功能：
        - 将日志解析为JSON数组
        - 每条日志包含完整的9个字段

        说明：后台下载场景直接返回 HttpResponse。
        """
        import json
        from apps.system.log_models import LogParser
        from apps.common.infra.logger import get_log_path_from_config
        from pathlib import Path
        _ = request

        log_file_path = get_log_path_from_config()

        if not Path(log_file_path).exists():
            return HttpResponse("日志文件不存在", status=404)

        try:
            # 解析日志
            parser = LogParser(log_file_path)
            log_entries = list(parser.parse_file(limit=10000))  # 最多导出10000条
            log_entries.reverse()  # 最新的在前

            # 转换为JSON
            logs_data = []
            for idx, entry in enumerate(log_entries, start=1):
                logs_data.append({
                    "id": idx,
                    "timestamp": entry.timestamp,
                    "level": entry.level,
                    "type": entry.get_type(),
                    "source": entry.get_source(),
                    "message": entry.message,
                    "username": entry.username or None,
                    "account_id": entry.account_id,
                    "ip_address": entry.ip_address or None,
                })

            # 返回响应
            response = HttpResponse(
                json.dumps(logs_data, ensure_ascii=False, indent=2, default=str),
                content_type="application/json; charset=utf-8"
            )
            filename = f"system_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response

        except Exception as e:  # noqa: BLE001
            logger.error(f"导出日志文件失败(JSON): {e}")
            return HttpResponse(f"导出失败: {str(e)}", status=500)

    def export_single_log(self, request: HttpRequest, object_id: str, fmt: str) -> HttpResponse:
        """
        导出单条日志（详情页使用），支持 TXT/CSV/JSON

        说明：后台下载场景直接返回 HttpResponse，保留文件下载体验。
        """
        import csv
        import io
        from apps.common.infra.logger import get_log_path_from_config
        from pathlib import Path
        _ = request

        try:
            log_id = int(object_id)
        except (TypeError, ValueError):
            return HttpResponse("无效的日志ID", status=400)

        log_file_path = get_log_path_from_config()
        if not Path(log_file_path).exists():
            return HttpResponse("日志文件不存在", status=404)

        entry = self._find_log_entry_by_id(log_file_path, log_id)
        if not entry:
            return HttpResponse("日志不存在或已被轮转", status=404)

        try:
            if fmt == "txt":
                content = entry.to_plain()
                response = HttpResponse(content + "\n", content_type="text/plain; charset=utf-8")
                filename = f"log_{entry.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            elif fmt == "json":
                response = HttpResponse(
                    json.dumps(entry.to_json(), ensure_ascii=False, indent=2),
                    content_type="application/json; charset=utf-8",
                )
                filename = f"log_{entry.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            elif fmt == "csv":
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(["ID", "时间戳", "级别", "类型", "来源", "消息", "账户名", "账户ID", "IP地址"])
                writer.writerow([
                    entry.id,
                    entry.timestamp,
                    entry.level,
                    entry.get_type(),
                    entry.get_source(),
                    entry.message,
                    entry.username or "-",
                    entry.account_id or "-",
                    entry.ip_address or "-",
                ])
                response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8-sig")
                filename = f"log_{entry.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            else:
                return HttpResponse("不支持的导出格式", status=400)

            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response
        except Exception as e:  # noqa: BLE001
            logger.error(f"导出单条日志失败({fmt}): {e}")
            return HttpResponse(f"导出失败: {str(e)}", status=500)


# 不再独立注册 EmailVerificationCode，改为在 SystemLogCategoryAdmin 中统一管理
class EmailVerificationCodeAdmin(admin.ModelAdmin):
    """
    邮箱验证码日志管理：查看验证码的发送与使用情况

    功能：
    - 查看所有邮箱验证码的发送记录
    - 按场景、使用状态、邮箱筛选
    - 追踪验证码的有效性和使用情况
    - 只读模式，不允许手动创建或修改验证码

    业务场景：
    - 追踪用户注册、找回密码、绑定邮箱的验证码发送情况
    - 审计异常的验证码使用行为
    - 排查验证码相关问题
    """

    # 列表展示字段
    list_display = (
        "id",
        "email",
        "scene",
        "code_masked",
        "is_used",
        "is_expired_display",
        "created_at",
        "verified_at",
    )
    # 过滤条件
    list_filter = ("scene", "is_used", "created_at")
    # 搜索字段
    search_fields = ("email", "code")
    # 排序：按创建时间倒序
    ordering = ("-created_at",)
    # 每页显示数量
    list_per_page = 100
    # 只读字段
    readonly_fields = (
        "email",
        "scene",
        "code",
        "is_used",
        "expires_at",
        "verified_at",
        "created_at",
        "updated_at",
    )

    @admin.display(description="验证码", ordering="code")
    def code_masked(self, obj: EmailVerificationCode) -> str:
        """脱敏显示验证码：只显示前2位和后2位"""
        if len(obj.code) > 4:
            return f"{obj.code[:2]}**{obj.code[-2:]}"
        return "****"

    @admin.display(description="是否过期", boolean=True)
    def is_expired_display(self, obj: EmailVerificationCode) -> bool:
        """显示验证码是否已过期"""
        return obj.is_expired

    # 禁用所有写操作
    def has_add_permission(self, request: HttpRequest) -> bool:
        """禁止手动添加验证码"""
        return False

    def has_change_permission(self, request: HttpRequest, obj=None) -> bool:
        """禁止修改验证码"""
        return False

    def has_delete_permission(self, request: HttpRequest, obj=None) -> bool:
        """禁止删除验证码记录"""
        return False


# 不再独立注册 AdminActionLog，改为在 SystemLogCategoryAdmin 中统一管理
class AdminActionLogAdmin(admin.ModelAdmin):
    """
    管理员操作日志管理：查看所有管理员的增删改操作记录

    功能：
    - 查看所有管理员（包括超级管理员）的操作记录
    - 按操作人、操作类型、模型类型筛选
    - 查看操作的详细变更内容
    - 追踪敏感操作的责任人和时间
    - 只读模式，不允许修改或删除日志

    业务场景：
    - 审计管理员操作，追溯敏感变更
    - 排查配置错误或数据异常的原因
    - 安全合规要求的操作审计
    """

    # 列表展示字段
    list_display = (
        "id",
        "created_at",
        "username",
        "action_type",
        "content_type",
        "object_repr",
        "ip_address",
    )
    # 过滤条件
    list_filter = ("action_type", "content_type", "created_at")
    # 搜索字段
    search_fields = ("username", "object_repr", "message", "ip_address")
    # 排序：按时间倒序
    ordering = ("-created_at",)
    # 每页显示数量
    list_per_page = 100
    # 只读字段
    readonly_fields = (
        "user",
        "username",
        "action_type",
        "content_type",
        "object_id",
        "object_repr",
        "changes",
        "message",
        "ip_address",
        "user_agent",
        "created_at",
    )

    # 详情页显示字段分组
    fieldsets = (
        ("操作信息", {
            "fields": ("created_at", "action_type", "message")
        }),
        ("操作人信息", {
            "fields": ("user", "username", "ip_address", "user_agent")
        }),
        ("操作对象", {
            "fields": ("content_type", "object_id", "object_repr")
        }),
        ("变更详情", {
            "fields": ("changes",),
            "classes": ("collapse",),  # 默认折叠
        }),
    )

    # 禁用所有写操作
    def has_add_permission(self, request: HttpRequest) -> bool:
        """禁止手动添加日志"""
        _ = request
        return False

    def has_change_permission(self, request: HttpRequest, obj=None) -> bool:
        """禁止修改日志"""
        _ = request
        _ = obj
        return False

    def has_delete_permission(self, request: HttpRequest, obj=None) -> bool:
        """禁止删除日志"""
        _ = request
        _ = obj
        return False


# 注释掉：已改为直接注册SystemLogAdmin，不再使用分类页面
# @admin.register(SystemLogCategory)
class SystemLogCategoryAdmin(admin.ModelAdmin):
    """
    系统日志统一入口管理

    功能：
    - 提供统一的日志分类导航页面
    - 显示"日志类型 | 说明"两列列表
    - 点击日志类型后跳转到对应的详细日志列表
    - 管理三类日志：邮箱验证码、管理员操作、系统运行日志

    实现：
    - 使用标准的 Django Admin changelist 样式
    - 添加自定义 URL 处理各类日志的详情页
    - 复用独立的 Admin 类（SystemLogAdmin、EmailVerificationCodeAdmin、AdminActionLogAdmin）
    """

    # 列表展示字段：日志类型（带链接）| 说明
    list_display = ("category_name_link", "description")

    # 禁用搜索、过滤、排序
    search_fields = []
    list_filter = []
    ordering = []

    # 禁用所有写操作
    def has_add_permission(self, request: HttpRequest) -> bool:
        """禁止添加"""
        _ = request
        return False

    def has_change_permission(self, request: HttpRequest, obj=None) -> bool:
        """禁止修改"""
        _ = request
        _ = obj
        return False

    def has_delete_permission(self, request: HttpRequest, obj=None) -> bool:
        """禁止删除"""
        _ = request
        _ = obj
        return False

    def get_queryset(self, request: HttpRequest):
        """
        返回日志分类列表

        不从数据库读取，而是返回硬编码的日志分类
        """
        categories = [
            SystemLogCategory(
                id=1,
                category_name="邮箱验证码",
                description="查看邮箱验证码的发送与使用情况，用于追踪注册、找回密码、绑定邮箱等操作"
            ),
            SystemLogCategory(
                id=2,
                category_name="管理员操作",
                description="查看所有管理员的增删改操作记录，用于审计和追溯敏感操作"
            ),
            SystemLogCategory(
                id=3,
                category_name="系统运行日志",
                description="查看系统运行时的日志记录，包括请求、错误、业务操作等信息"
            ),
        ]

        # 标记为已存在的对象
        for cat in categories:
            cat._state.adding = False  # type: ignore[attr-defined]

        # 返回伪造的 QuerySet
        class FakeQuery:
            """伪造的 Query 对象"""
            select_related = False
            order_by = []

        class FakeQuerySet(list):
            """伪造的 QuerySet"""

            def __init__(self, data):
                super().__init__(data)
                self.model = SystemLogCategory
                self.ordered = True
                self._result_cache = data
                self.query = FakeQuery()

            def count(self, *args, **kwargs):  # type: ignore[override]
                _ = args
                _ = kwargs
                return len(self)

            def order_by(self, *args, **kwargs):  # type: ignore[override]
                _ = args
                _ = kwargs
                return self

            def filter(self, *args, **kwargs):  # type: ignore[override]
                _ = args
                _ = kwargs
                return self

            def exclude(self, *args, **kwargs):  # type: ignore[override]
                _ = args
                _ = kwargs
                return self

            def all(self):
                return self

            def distinct(self, *args, **kwargs):  # type: ignore[override]
                _ = args
                _ = kwargs
                return self

            def values_list(self, *fields, **kwargs):  # type: ignore[override]
                flat = kwargs.get('flat', False)
                if not fields:
                    return []
                field_name = fields[0]
                values = []
                for obj in self:
                    value = getattr(obj, field_name, None)
                    if value and value not in values:
                        values.append(value)
                if flat:
                    return values
                return [(v,) for v in values]

            def values(self, *fields):  # type: ignore[override]
                result = []
                for obj in self:
                    item = {}
                    for field in fields:
                        item[field] = getattr(obj, field, None)
                    result.append(item)
                return result

            def exists(self):
                return len(self) > 0

            @staticmethod
            def none():
                return FakeQuerySet([])

            def using(self, alias):
                _ = alias
                return self

            def select_related(self, *args):
                _ = args
                return self

            def prefetch_related(self, *args):
                _ = args
                return self

            def _clone(self):  # type: ignore[override]
                """克隆 QuerySet（Django Admin 需要）"""
                return self

        return FakeQuerySet(categories)

    @admin.display(description='日志类型')
    def category_name_link(self, obj):
        """
        渲染带链接的日志类型

        根据日志类型 ID，返回不同的跳转链接
        """
        from django.utils.html import format_html
        from django.urls import reverse

        # 根据 ID 确定跳转的 URL
        if obj.id == 1:
            url = reverse('admin:system_systemlogcategory_email_codes')
        elif obj.id == 2:
            url = reverse('admin:system_systemlogcategory_admin_actions')
        elif obj.id == 3:
            url = reverse('admin:system_systemlogcategory_runtime_logs')
        else:
            return obj.category_name

        # 返回带链接的 HTML
        # noinspection PyDeprecation
        return format_html('<a href="{url}">{name}</a>', url=url, name=obj.category_name)

    def get_urls(self):
        """添加自定义 URL：各类日志的详情页"""
        from django.urls import path

        urls = super().get_urls()
        custom_urls = [
            path(
                'email-verification-codes/',
                self.admin_site.admin_view(self.email_verification_codes_view),
                name='system_systemlogcategory_email_codes'
            ),
            path(
                'admin-action-logs/',
                self.admin_site.admin_view(self.admin_action_logs_view),
                name='system_systemlogcategory_admin_actions'
            ),
            path(
                'system-runtime-logs/',
                self.admin_site.admin_view(self.system_runtime_logs_view),
                name='system_systemlogcategory_runtime_logs'
            ),
        ]
        return custom_urls + urls

    def email_verification_codes_view(self, request):
        """邮箱验证码详情页"""
        # 实例化独立的 Admin 类
        email_admin = EmailVerificationCodeAdmin(EmailVerificationCode, self.admin_site)
        # 调用其 changelist_view
        return email_admin.changelist_view(request)

    def admin_action_logs_view(self, request):
        """管理员操作日志详情页"""
        action_admin = AdminActionLogAdmin(AdminActionLog, self.admin_site)
        return action_admin.changelist_view(request)

    def system_runtime_logs_view(self, request):
        """系统运行日志详情页"""
        log_admin = SystemLogAdmin(SystemLog, self.admin_site)
        return log_admin.changelist_view(request)
