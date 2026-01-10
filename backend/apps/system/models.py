from __future__ import annotations

import json
from typing import Any

from django.db import models
from django.core.exceptions import ValidationError


class SystemConfig(models.Model):
    """
    系统配置项模型
    - 场景：允许管理员在后台为可覆盖的系统参数设置运行期值，优先于 .env/settings
    - 约束：仅存储可运行期覆盖的业务参数，启动依赖仍需 .env 提供
    """

    class ValueType(models.TextChoices):
        STRING = "string", "字符串"
        INT = "int", "整数"
        BOOL = "bool", "布尔"
        JSON = "json", "JSON"
        SECRET = "secret", "字符串"

    key = models.CharField("键", max_length=120, unique=True, db_index=True)
    value = models.TextField("配置值")
    value_type = models.CharField(
        "值类型", max_length=20, choices=ValueType.choices, default=ValueType.STRING
    )
    description = models.TextField("说明", blank=True)
    detail_description = models.TextField("详细用途说明", blank=True, default="")
    is_sensitive = models.BooleanField(
        "敏感字段",
        default=False,
        help_text="后台仅展示脱敏值 ' *** '",
    )
    is_required = models.BooleanField(
        "必填",
        default=False,
        help_text="此配置为必填项，缺失可能导致平台不可用",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "SYSTEM"
        verbose_name_plural = "系统配置"
        ordering = ["key"]

    def __str__(self) -> str:
        """后台对象显示使用键名，便于识别"""
        return self.key

    def cast_value(self) -> Any:
        """根据类型转换配置值"""
        if self.value_type == self.ValueType.INT:
            try:
                return int(self.value)
            except (TypeError, ValueError):
                return self.value
        if self.value_type == self.ValueType.BOOL:
            return str(self.value).strip().lower() in {"1", "true", "yes", "on"}
        if self.value_type == self.ValueType.JSON:
            try:
                return json.loads(self.value)
            except json.JSONDecodeError:
                return self.value
        # SECRET / STRING 默认返回原值
        return self.value

    @property
    def display_value(self) -> str:
        """后台展示值：敏感字段脱敏处理"""
        if self.is_sensitive and self.value:
            return "******"
        return str(self.value)


class MailAccountQuerySet(models.QuerySet):
    """
    发信账号 QuerySet：封装启用状态与默认账号的获取

    业务场景：
    - 获取所有已启用的发信账号
    - 获取默认发信账号（优先级最高的启用账号）
    """

    def active(self):
        """
        获取已启用的发信账号列表

        返回：
        - 所有 is_active=True 的发信账号
        """
        return self.filter(is_active=True)

    def get_default(self):
        """
        获取默认发信账号，若无默认则按优先级取第一个启用账号

        优先级：
        1. is_default=True 的账号
        2. 按 priority 升序、updated_at 降序排序的第一个启用账号

        返回：
        - 默认发信账号，若无可用账号则返回 None
        """
        account = (
            self.active()
            .filter(is_default=True)
            .order_by("priority", "-updated_at")
            .first()
        )
        if account:
            return account
        return self.active().order_by("priority", "-updated_at").first()


class MailAccount(models.Model):
    """
    可配置的发信邮箱账户，支持不同服务商

    业务场景：
    - 统一管理平台发信 SMTP 账户，供验证码/通知邮件使用
    - 支持多个 SMTP 账号、优先级、默认账号切换

    模块角色：
    - 存储发信配置、优先级与默认标记
    - 被邮件发送组件选择（email_sender.py）

    功能：
    - 预置常用服务商默认参数（QQ/163/Gmail/Outlook）
    - 保存时保证默认账号唯一（自动取消其他账号的默认标记）
    - 自动补充 from_email 默认值（等于 username）

    注意：
    - 迁移自 accounts 模块，现在属于系统级别的基础设施配置
    - 在 Django Admin 后台的 SYSTEM 模块中管理
    """

    class Provider(models.TextChoices):
        """邮件服务商枚举"""
        QQ = "qq", "QQ 邮箱"
        NETEASE_163 = "163", "163 邮箱"
        GMAIL = "gmail", "Gmail"
        OUTLOOK = "outlook", "Outlook 邮箱"
        CUSTOM = "custom", "自定义 SMTP"

    provider = models.CharField("服务商", max_length=20, choices=Provider.choices, default=Provider.QQ)
    name = models.CharField("名称", max_length=50, help_text="后台展示用名称")
    host = models.CharField("SMTP 主机", max_length=120)
    port = models.PositiveIntegerField("端口", default=587)
    use_tls = models.BooleanField("启用 TLS", default=True)
    use_ssl = models.BooleanField("启用 SSL", default=False)
    username = models.EmailField("用户名", help_text="邮箱账号")
    password = models.CharField("密码", max_length=255, help_text="授权码或应用专用密码")
    from_name = models.CharField("发信名称", max_length=100, blank=True, help_text="展示名")
    from_email = models.EmailField("发信邮箱", blank=True, help_text="用于 From 的邮箱地址，固定等于用户名")
    priority = models.PositiveIntegerField("优先级", default=100, help_text="数字越小优先级越高")
    is_active = models.BooleanField("启用", default=True)
    is_default = models.BooleanField(
        "默认账号",
        default=False,
        help_text="设为 True 后其余账号将自动取消默认"
    )
    verification_subject = models.CharField(
        "邮件主题",
        max_length=120,
        default="",
        blank=True,
        help_text="用于邮箱验证码的邮件主题，留空则使用默认“您的验证码”"
    )
    verification_expire_minutes = models.PositiveIntegerField(
        "验证码有效时间（分钟）",
        default=10,
        help_text="单位分钟，使用默认 10 分钟，必须为正整数"
    )
    support_email = models.EmailField(
        "支持邮箱",
        blank=True,
        default="",
        help_text="留空则默认等于用户名，用于邮件页脚的联系邮箱"
    )
    site_url = models.URLField(
        "网站链接",
        blank=True,
        default="",
        help_text="可选，填写后邮件页脚展示站点链接"
    )
    logo = models.ImageField(
        "Logo",
        upload_to="mail_logos/",
        blank=True,
        null=True,
        help_text="可选，上传后作为验证码邮件 Logo 展示"
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    objects = MailAccountQuerySet.as_manager()

    class Meta:
        ordering = ["priority", "-updated_at"]
        verbose_name = "发信账号"
        verbose_name_plural = "发信账号"

    # 常用服务商的默认配置（主机、端口、TLS/SSL）
    PROVIDER_DEFAULTS = {
        Provider.QQ: {"host": "smtp.qq.com", "port": 587, "use_tls": True, "use_ssl": False},
        Provider.NETEASE_163: {"host": "smtp.163.com", "port": 465, "use_tls": False, "use_ssl": True},
        Provider.GMAIL: {"host": "smtp.gmail.com", "port": 587, "use_tls": True, "use_ssl": False},
        Provider.OUTLOOK: {"host": "smtp.office365.com", "port": 587, "use_tls": True, "use_ssl": False},
    }

    def apply_provider_defaults(self):
        """
        占位方法：不再自动填充主机端口，避免覆盖手工配置

        历史：
        - 旧版本会根据 provider 自动填充 host/port/tls/ssl
        - 现在保留此方法为空，避免破坏已有配置
        """
        return

    def save(self, *args, **kwargs):
        """
        保存前填充默认配置、默认发信邮箱，并确保默认账号唯一

        逻辑：
        1. 调用 apply_provider_defaults()（当前为空）
        2. 固定使用 username 作为发信邮箱，忽略手动配置，避免 From 漂移
        3. 校验 host 不能为空（必填）
        4. 保存到数据库
        5. 若当前账号设为默认，则取消其他账号的默认标记
        """
        self.apply_provider_defaults()

        # 强制使用用户名作为发信邮箱，避免管理员误填导致退信
        self.from_email = self.username

        # 校验必填字段
        if not self.host:
            raise ValidationError("SMTP 主机不能为空，请选择服务商或手动填写")

        # 保存到数据库
        super().save(*args, **kwargs)

        # 确保默认账号唯一：若当前账号设为默认，取消其他账号的默认标记
        if self.is_default:
            MailAccount.objects.exclude(pk=self.pk).update(is_default=False)

    @property
    def from_display(self) -> str:
        """
        格式化发信人展示，例如 Name <email>

        返回：
        - 若有 from_name，返回 "Name <username>" 格式
        - 否则仅返回 username
        """
        if self.from_name:
            return f"{self.from_name} <{self.username}>"
        return self.username

    def __str__(self) -> str:
        """后台展示使用名称，便于管理员快速识别账号"""
        return self.name or self.username


class SystemLogCategory(models.Model):
    """
    系统日志分类入口（非数据库模型）

    业务场景：
    - 提供统一的日志分类导航入口
    - 在后台显示所有可用的日志类型及说明
    - 点击日志类型后跳转到对应的详细日志列表

    注意：
    - 这是一个虚拟模型，不对应数据库表
    - 仅用于在 Admin 中展示日志分类导航
    """

    # 虚拟字段，不会存储到数据库
    id = models.IntegerField(primary_key=True)
    category_name = models.CharField("日志类型", max_length=100)
    description = models.TextField("说明")

    class Meta:
        managed = False  # 不创建数据库表
        db_table = "system_log_category_view"
        verbose_name = "SYSTEM"
        verbose_name_plural = "系统日志"

    def __str__(self):
        return self.category_name


class SystemLog(models.Model):
    """
    系统运行日志（非数据库模型）

    用途：
    - 用于在 Django Admin 中展示日志文件内容
    - 不对应实际数据库表（managed=False），数据从日志文件读取
    - 提供查看和导出系统日志的功能

    注意：
    - 继承 models.Model 以满足 Django Admin 要求
    - managed=False 表示不创建数据库表
    - Admin 中需要自定义 queryset 来读取日志文件
    """

    # 定义字段（仅用于 Admin 展示，不实际存储到数据库）
    timestamp = models.CharField("时间", max_length=50)
    level = models.CharField("级别", max_length=20)
    logger = models.CharField("记录器", max_length=100)
    message = models.TextField("消息")
    request_id = models.CharField("请求ID", max_length=50, blank=True)
    user_id = models.CharField("用户ID", max_length=50, blank=True)
    ip = models.CharField("IP地址", max_length=50, blank=True)
    path = models.CharField("路径", max_length=200, blank=True)
    method = models.CharField("方法", max_length=10, blank=True)
    user_agent = models.CharField("User-Agent", max_length=200, blank=True)
    raw_line = models.TextField("原始日志", blank=True)

    class Meta:
        """元数据配置"""
        verbose_name = "SYSTEM"
        verbose_name_plural = "系统日志"
        # 标记为非数据库模型：不创建表、不执行迁移
        managed = False
        # 避免 Django 尝试创建表时报错
        db_table = "system_log_view"

    def __str__(self) -> str:
        """Admin 列表显示使用"""
        return f"[{self.level}] {self.timestamp} - {self.message[:50]}"


class EmailVerificationCode(models.Model):
    """
    邮箱验证码记录（已从 accounts 模块迁移）

    业务场景：
    - 注册、找回密码、绑定邮箱等操作的验证码校验
    - 属于系统级别的安全日志

    迁移说明：
    - 原本在 accounts 模块，现迁移到 system 作为系统日志的一部分
    - 数据库表名保持为 accounts_emailverificationcode（不改表名，避免数据丢失）
    """

    class Scene(models.TextChoices):
        """验证码使用场景"""
        REGISTER = "register", "注册"
        RESET_PASSWORD = "reset_password", "找回密码"
        BIND_EMAIL = "bind_email", "绑定邮箱"
        CHANGE_PASSWORD = "change_password", "修改密码"

    email = models.EmailField("邮箱")
    scene = models.CharField("场景", max_length=32, choices=Scene.choices)
    code = models.CharField("验证码", max_length=6)
    is_used = models.BooleanField("是否已使用", default=False)
    expires_at = models.DateTimeField("过期时间")
    verified_at = models.DateTimeField("验证时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        # 保持原表名，避免数据迁移问题
        db_table = "accounts_emailverificationcode"
        indexes = [
            models.Index(fields=["email", "scene", "is_used"]),
            models.Index(fields=["scene", "created_at"]),
        ]
        ordering = ["-created_at"]
        verbose_name = "SYSTEM"
        verbose_name_plural = "系统日志 - 邮箱验证码"

    def __str__(self) -> str:
        return f"{self.email} ({self.get_scene_display()})"

    @property
    def is_expired(self) -> bool:
        """是否已过期：供校验逻辑快速判断有效性"""
        from django.utils import timezone
        return timezone.now() >= self.expires_at

    def mark_used(self) -> None:
        """标记验证码已使用并记录验证时间"""
        from django.utils import timezone
        self.is_used = True
        self.verified_at = timezone.now()
        self.save(update_fields=["is_used", "verified_at", "updated_at"])


class AdminActionLog(models.Model):
    """
    管理员操作日志

    业务场景：
    - 记录所有管理员（包括超级管理员）在后台的增删改操作
    - 用于审计和追溯敏感操作
    - 不记录查看（GET）操作，只记录修改性操作

    记录内容：
    - 操作人、操作时间、操作类型（增/删/改）
    - 操作的模型、对象ID、对象描述
    - 操作前后的数据变化（可选）
    - 客户端 IP、User-Agent
    """

    class ActionType(models.TextChoices):
        """操作类型"""
        CREATE = "create", "创建"
        UPDATE = "update", "修改"
        DELETE = "delete", "删除"

    # 操作人信息
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="操作人",
        help_text="执行操作的管理员"
    )
    username = models.CharField("用户名", max_length=150, help_text="操作人用户名快照")

    # 操作内容
    action_type = models.CharField("操作类型", max_length=10, choices=ActionType.choices)
    content_type = models.CharField("模型类型", max_length=100, help_text="例如：User, Contest, Challenge")
    object_id = models.CharField("对象ID", max_length=100, blank=True, help_text="被操作对象的ID")
    object_repr = models.CharField("对象描述", max_length=200, help_text="被操作对象的字符串表示")

    # 详细信息
    changes = models.JSONField("变更详情", blank=True, null=True, help_text="操作前后的数据对比（JSON格式）")
    message = models.TextField("操作说明", blank=True, help_text="操作的详细说明或备注")

    # 请求信息
    ip_address = models.GenericIPAddressField("IP地址", null=True, blank=True)
    user_agent = models.CharField("User-Agent", max_length=255, blank=True)

    # 时间戳
    created_at = models.DateTimeField("操作时间", auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["action_type", "created_at"]),
            models.Index(fields=["content_type", "created_at"]),
        ]
        ordering = ["-created_at"]
        verbose_name = "SYSTEM"
        verbose_name_plural = "系统日志 - 管理员操作"

    def __str__(self) -> str:
        return f"{self.username} {self.get_action_type_display()} {self.content_type} ({self.created_at.strftime('%Y-%m-%d %H:%M:%S')})"
