"""
账户相关模型定义（用户、邮件验证码、邮件账号等）。

- 扩展 User 模型（昵称、头像、组织、账号类型等）并覆写 Manager 约束超管数量。
- 邮件验证码模型支持多场景存储、过期与标记已使用。
- 邮件账号模型封装 SMTP 配置、默认账号切换逻辑。
"""

from __future__ import annotations

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.utils import timezone


class FTCUserManager(UserManager):
    """
    自定义用户管理器：
    - 限制超管数量，防止过多高权限账户。
    - 创建超管时补齐账户类型和 staff 标志。
    """

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        """创建超管，附带数量上限校验与默认权限标志。"""
        if self.filter(is_superuser=True).count() >= 3:
            raise ValueError("Superuser limit reached (maximum 3). Use existing accounts.")
        extra_fields.setdefault("account_type", self.model.AccountType.ADMIN)
        extra_fields.setdefault("is_staff", True)
        return super().create_superuser(username, email=email, password=password, **extra_fields)


class User(AbstractUser):
    class AccountType(models.TextChoices):
        USER = "user", "普通用户"
        ADMIN = "admin", "管理员"

    """
    FTC 自定义用户模型，扩展基础资料。
    """

    email = models.EmailField("邮箱", unique=True)
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
        if not self.nickname:
            self.nickname = self.username
        super().save(*args, **kwargs)

    @property
    def display_name(self) -> str:
        """展示名：优先昵称，否则回退用户名。"""
        return self.nickname or self.username


class EmailVerificationCode(models.Model):
    """
    邮箱验证码记录，支持注册/找回密码等不同场景。
    """

    class Scene(models.TextChoices):
        REGISTER = "register", "注册"
        RESET_PASSWORD = "reset_password", "找回密码"
        BIND_EMAIL = "bind_email", "绑定邮箱"

    email = models.EmailField("邮箱")
    scene = models.CharField("场景", max_length=32, choices=Scene.choices)
    code = models.CharField("验证码", max_length=6)
    is_used = models.BooleanField("是否已使用", default=False)
    expires_at = models.DateTimeField("过期时间")
    verified_at = models.DateTimeField("验证时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

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
        return timezone.now() >= self.expires_at

    def mark_used(self) -> None:
        self.is_used = True
        self.verified_at = timezone.now()
        self.save(update_fields=["is_used", "verified_at", "updated_at"])


class PlayerUser(User):
    class Meta:
        proxy = True
        verbose_name = "用户"
        verbose_name_plural = "用户"


class StaffUser(User):
    class Meta:
        proxy = True
        verbose_name = "管理员"
        verbose_name_plural = "管理员"


class MailAccountQuerySet(models.QuerySet):
    """发信账号 QuerySet：封装启用状态与默认账号的获取。"""

    def active(self):
        return self.filter(is_active=True)

    def get_default(self):
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
    可配置的发信邮箱账户，支持不同服务商。
    """

    class Provider(models.TextChoices):
        QQ = "qq", "QQ 邮箱"
        NETEASE_163 = "163", "163 邮箱"
        GMAIL = "gmail", "Gmail"
        OUTLOOK = "outlook", "Outlook 邮箱"
        CUSTOM = "custom", "自定义 SMTP"

    provider = models.CharField("服务商", max_length=20, choices=Provider.choices, default=Provider.QQ)
    name = models.CharField("名称", max_length=50, help_text="后台展示用名称")
    host = models.CharField("SMTP 主机", max_length=120, blank=True)
    port = models.PositiveIntegerField("端口", default=587)
    use_tls = models.BooleanField("启用 TLS", default=True)
    use_ssl = models.BooleanField("启用 SSL", default=False)
    username = models.EmailField("用户名", help_text="邮箱账号")
    password = models.CharField("密码", max_length=255, help_text="授权码或应用专用密码")
    from_name = models.CharField("发信名称", max_length=100, blank=True, help_text="展示名")
    from_email = models.EmailField("发信邮箱", blank=True, help_text="用于 From 的邮箱地址，默认等于 username")
    priority = models.PositiveIntegerField("优先级", default=100, help_text="数字越小优先级越高")
    is_active = models.BooleanField("启用", default=True)
    is_default = models.BooleanField("默认账号", default=False, help_text="设为 True 后其余账号将自动取消默认")
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

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
        self.apply_provider_defaults()
        if not self.from_email:
            self.from_email = self.username
        super().save(*args, **kwargs)
        if self.is_default:
            MailAccount.objects.exclude(pk=self.pk).update(is_default=False)

    @property
    def from_display(self) -> str:
        if self.from_name:
            return f"{self.from_name} <{self.from_email}>"
        return self.from_email
