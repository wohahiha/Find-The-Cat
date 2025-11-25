"""
账户相关模型定义（用户、邮件验证码、邮件账号等）。

- 扩展 User 模型（昵称、头像、组织、账号类型等）并覆写 Manager 限制超管数量，满足安全与资料需求。
- 邮件验证码模型支持注册/重置密码/绑定邮箱等场景，内置过期与已使用标记。
- 邮件账号模型封装 SMTP 配置、默认账号切换与优先级，支撑统一邮件发送基础设施。
"""

from __future__ import annotations

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.utils import timezone


class FTCUserManager(UserManager):
    """
    自定义用户管理器：
    - 业务场景：创建超级管理员时限制数量，避免超管过多带来风险。
    - 模块角色：为 User 模型提供带业务约束的创建入口。
    - 功能：创建超管时补齐账号类型/管理员标记，超出上限直接拒绝。
    """

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        """创建超管：附带数量上限校验与默认权限标志。"""
        if self.filter(is_superuser=True).count() >= 3:
            raise ValueError("Superuser limit reached (maximum 3). Use existing accounts.")
        extra_fields.setdefault("account_type", self.model.AccountType.ADMIN)
        extra_fields.setdefault("is_staff", True)
        return super().create_superuser(username, email=email, password=password, **extra_fields)


class User(AbstractUser):
    """
    FTC 自定义用户模型：
    - 业务场景：承载选手与管理员的认证主体，存储扩展资料。
    - 模块角色：被认证、权限、业务服务和邮件发送广泛引用。
    - 功能：增加昵称、头像、组织等字段；账号类型标记用户/管理员；保存时自动填充昵称。
    """

    class AccountType(models.TextChoices):
        USER = "user", "普通用户"
        ADMIN = "admin", "管理员"

    email = models.EmailField("邮箱", unique=True)  # 唯一邮箱，作为登录/通知的主标识
    nickname = models.CharField(
        "昵称",
        max_length=40,
        blank=True,
        help_text="昵称，默认等于用户名，可由选手自行修改",
    )
    avatar = models.URLField(
        "头像",
        blank=True,
        help_text="头像链接，前端可使用对象存储上传后回填",
    )
    bio = models.TextField(
        "个人简介",
        blank=True,
        help_text="个人简介（个性签名）",
    )
    organization = models.CharField(
        "所属单位",
        max_length=120,
        blank=True,
        help_text="所属团队 / 学校 / 公司 / 组织",
    )
    country = models.CharField("国家/地区", max_length=64, blank=True, help_text="国家/地区，便于排行榜展示")
    website = models.URLField("个人主页", blank=True, help_text="个人主页或其他社交链接")
    is_email_verified = models.BooleanField("邮箱已验证", default=False, help_text="邮箱是否已通过验证码验证")
    updated_at = models.DateTimeField("更新时间", auto_now=True)
    account_type = models.CharField("账号类型", max_length=10, choices=AccountType.choices, default=AccountType.USER, db_index=True)

    objects = FTCUserManager()

    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["email"]

    class Meta(AbstractUser.Meta):  # type: ignore[misc]
        ordering = ["-date_joined"]
        verbose_name = "用户"
        verbose_name_plural = "用户"

    def save(self, *args, **kwargs):
        """保存前自动补充昵称，避免空昵称影响展示。"""
        if not self.nickname:
            self.nickname = self.username
        super().save(*args, **kwargs)

    @property
    def display_name(self) -> str:
        """展示名：优先昵称，否则回退用户名。"""
        return self.nickname or self.username


class EmailVerificationCode(models.Model):
    """
    邮箱验证码记录：
    - 业务场景：注册、找回密码、绑定邮箱等操作的验证码校验。
    - 模块角色：验证码存储与状态管理，被发送/校验服务调用。
    - 功能：记录验证码、场景、过期与使用状态，提供过期判断与使用标记。
    """

    class Scene(models.TextChoices):
        REGISTER = "register", "注册"
        RESET_PASSWORD = "reset_password", "找回密码"
        BIND_EMAIL = "bind_email", "绑定邮箱"

    email = models.EmailField("邮箱")  # 目标邮箱地址
    scene = models.CharField("场景", max_length=32, choices=Scene.choices)  # 使用场景：注册/重置/绑定
    code = models.CharField("验证码", max_length=6)  # 实际验证码内容
    is_used = models.BooleanField("是否已使用", default=False)  # 是否已被消费
    expires_at = models.DateTimeField("过期时间")  # 过期时间点
    verified_at = models.DateTimeField("验证时间", null=True, blank=True)  # 验证通过的时间
    created_at = models.DateTimeField("创建时间", auto_now_add=True)  # 记录创建时间
    updated_at = models.DateTimeField("更新时间", auto_now=True)  # 记录更新时间

    class Meta:
        indexes = [
            models.Index(fields=["email", "scene", "is_used"]),
            models.Index(fields=["scene", "created_at"]),
        ]
        ordering = ["-created_at"]
        verbose_name = "邮箱验证码"
        verbose_name_plural = "邮箱验证码"

    def __str__(self) -> str:
        return f"{self.email} ({self.scene})"

    @property
    def is_expired(self) -> bool:
        """是否已过期：供校验逻辑快速判断有效性。"""
        return timezone.now() >= self.expires_at

    def mark_used(self) -> None:
        """标记验证码已使用并记录验证时间。"""
        self.is_used = True
        self.verified_at = timezone.now()
        self.save(update_fields=["is_used", "verified_at", "updated_at"])


class PlayerUser(User):
    """选手代理模型：复用 User 表，便于在管理端按角色区分。"""

    class Meta:
        proxy = True
        verbose_name = "用户"
        verbose_name_plural = "用户"


class StaffUser(User):
    """管理员代理模型：复用 User 表，在管理端聚焦管理员列表。"""

    class Meta:
        proxy = True
        verbose_name = "管理员"
        verbose_name_plural = "管理员"


class MailAccountQuerySet(models.QuerySet):
    """发信账号 QuerySet：封装启用状态与默认账号的获取。"""

    def active(self):
        """获取已启用的发信账号列表。"""
        return self.filter(is_active=True)

    def get_default(self):
        """获取默认发信账号，若无默认则按优先级取第一个启用账号。"""
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
    可配置的发信邮箱账户，支持不同服务商：
    - 业务场景：统一管理平台发信 SMTP 账户，供验证码/通知邮件使用。
    - 模块角色：存储发信配置、优先级与默认标记，被邮件发送组件选择。
    - 功能：预置常用服务商默认参数，保存时保证默认账号唯一。
    """

    class Provider(models.TextChoices):
        QQ = "qq", "QQ 邮箱"
        NETEASE_163 = "163", "163 邮箱"
        GMAIL = "gmail", "Gmail"
        OUTLOOK = "outlook", "Outlook 邮箱"
        CUSTOM = "custom", "自定义 SMTP"

    provider = models.CharField("服务商", max_length=20, choices=Provider.choices, default=Provider.QQ)  # 邮件服务商
    name = models.CharField("名称", max_length=50, help_text="后台展示用名称")  # 后台展示名称
    host = models.CharField("SMTP 主机", max_length=120, blank=True)  # SMTP 主机地址
    port = models.PositiveIntegerField("端口", default=587)  # SMTP 端口
    use_tls = models.BooleanField("启用 TLS", default=True)  # 是否启用 TLS
    use_ssl = models.BooleanField("启用 SSL", default=False)  # 是否启用 SSL
    username = models.EmailField("用户名", help_text="邮箱账号")  # 登录邮箱
    password = models.CharField("密码", max_length=255, help_text="授权码或应用专用密码")  # 授权码/密码
    from_name = models.CharField("发信名称", max_length=100, blank=True, help_text="展示名")  # 发信展示名
    from_email = models.EmailField("发信邮箱", blank=True, help_text="用于 From 的邮箱地址，默认等于 username")  # 发件人邮箱
    priority = models.PositiveIntegerField("优先级", default=100, help_text="数字越小优先级越高")  # 选用优先级
    is_active = models.BooleanField("启用", default=True)  # 是否启用账号
    is_default = models.BooleanField("默认账号", default=False, help_text="设为 True 后其余账号将自动取消默认")  # 是否为默认账号
    created_at = models.DateTimeField("创建时间", auto_now_add=True)  # 创建时间
    updated_at = models.DateTimeField("更新时间", auto_now=True)  # 更新时间

    objects = MailAccountQuerySet.as_manager()

    class Meta:
        ordering = ["priority", "-updated_at"]
        verbose_name = "发信账号"
        verbose_name_plural = "发信账号"

    PROVIDER_DEFAULTS = {
        Provider.QQ: {"host": "smtp.qq.com", "port": 587, "use_tls": True, "use_ssl": False},
        Provider.NETEASE_163: {"host": "smtp.163.com", "port": 465, "use_tls": False, "use_ssl": True},
        Provider.GMAIL: {"host": "smtp.gmail.com", "port": 587, "use_tls": True, "use_ssl": False},
        Provider.OUTLOOK: {"host": "smtp.office365.com", "port": 587, "use_tls": True, "use_ssl": False},
    }

    def apply_provider_defaults(self):
        """根据预置服务商填充默认 SMTP 配置。"""
        config = self.PROVIDER_DEFAULTS.get(self.provider)
        if not config:
            return
        if not self.host:
            self.host = config["host"]
        if self.port in (0, None):
            self.port = config["port"]
        if self.use_tls is None:
            self.use_tls = config["use_tls"]
        if self.use_ssl is None:
            self.use_ssl = config["use_ssl"]

    def save(self, *args, **kwargs):
        """保存前填充默认配置、默认发信邮箱，并确保默认账号唯一。"""
        self.apply_provider_defaults()
        if not self.from_email:
            self.from_email = self.username
        super().save(*args, **kwargs)
        if self.is_default:
            MailAccount.objects.exclude(pk=self.pk).update(is_default=False)

    @property
    def from_display(self) -> str:
        """格式化发信人展示，例如 Name <email>。"""
        if self.from_name:
            return f"{self.from_name} <{self.from_email}>"
        return self.from_email
