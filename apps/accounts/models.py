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
        # 数量限制：系统最多允许 3 个超级管理员
        if self.filter(is_superuser=True).count() >= 3:
            raise ValueError("Superuser limit reached (maximum 3). Use existing accounts.")
        # 默认设置账号类型为管理员
        extra_fields.setdefault("account_type", self.model.AccountType.ADMIN)
        # 默认开启 staff 标志，确保可登录后台
        extra_fields.setdefault("is_staff", True)
        return super().create_superuser(username, email=email, password=password, **extra_fields)


class User(AbstractUser):
    class AccountType(models.TextChoices):
        USER = "user", "普通用户"
        ADMIN = "admin", "管理员"

    """
    FTC 自定义用户模型，扩展基础资料并预留队伍相关字段。
    """

    # 唯一邮箱，作为登录与通知标识
    email = models.EmailField("邮箱", unique=True)
    # 昵称（可选），默认回填用户名
    nickname = models.CharField(
        "昵称",
        max_length=40,
        blank=True,
        help_text="昵称，默认等于用户名，可由选手自行修改",
    )
    # 头像链接（可选），配合对象存储回填
    avatar = models.URLField(
        "头像",
        blank=True,
        help_text="头像链接，前端可使用对象存储上传后回填",
    )
    # 个性签名/简介
    bio = models.TextField(
        "个人简介",
        blank=True,
        help_text="个人简介 / 个性签名",
    )
    # 所属单位/团队信息
    organization = models.CharField(
        "所属单位",
        max_length=120,
        blank=True,
        help_text="所属团队 / 学校 / 公司",
    )
    # 国家/地区，用于排行榜或统计
    country = models.CharField(
        "国家/地区",
        max_length=64,
        blank=True,
        help_text="国家/地区，便于排行榜展示",
    )
    # 个人主页或社交链接
    website = models.URLField(
        "个人主页",
        blank=True,
        help_text="个人主页或其他社交链接",
    )
    # 邮箱是否已验证，配合验证码流程
    is_email_verified = models.BooleanField(
        "邮箱已验证",
        default=False,
        help_text="邮箱是否已通过验证码验证",
    )
    # 是否队长，占位字段，后续由 Team 模块外键控制
    is_team_leader = models.BooleanField(
        "队长",
        default=False,
        help_text="是否担任当前队伍队长（Team 模块完善后会迁移为外键判断）",
    )
    # 队伍占位 UUID，将由 contests/teams 模块替换
    team_uuid = models.UUIDField(
        "队伍占位符",
        null=True,
        blank=True,
        help_text="所属队伍占位字段，后续 contests/teams 模块会替换为外键",
        db_index=True,
    )
    # 资料更新时间戳
    updated_at = models.DateTimeField("更新时间", auto_now=True)
    # 账号类型：普通用户/管理员，用于权限判断
    account_type = models.CharField(
        "账号类型",
        max_length=10,
        choices=AccountType.choices,
        default=AccountType.USER,
        db_index=True,
    )

    # 使用自定义管理员，替换默认 UserManager
    objects = FTCUserManager()

    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["email"]

    class Meta(AbstractUser.Meta):  # type: ignore[misc]
        ordering = ["-date_joined"]
        verbose_name = "用户"
        verbose_name_plural = "用户"

    def save(self, *args, **kwargs):
        """
        保存前的回填逻辑：
        - 若未填写昵称，自动使用用户名，确保展示名称不为空。
        """
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

    # 目标邮箱
    email = models.EmailField()
    # 验证场景：注册/重置/绑定
    scene = models.CharField(max_length=32, choices=Scene.choices)
    # 6 位验证码
    code = models.CharField(max_length=6)
    # 是否已使用，防止重复消费
    is_used = models.BooleanField(default=False)
    # 过期时间
    expires_at = models.DateTimeField()
    # 实际完成验证的时间
    verified_at = models.DateTimeField(null=True, blank=True)
    # 创建时间
    created_at = models.DateTimeField(auto_now_add=True)
    # 更新时间
    updated_at = models.DateTimeField(auto_now=True)

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
        """是否已过期：当前时间大于等于过期时间即视为过期。"""
        return timezone.now() >= self.expires_at

    def mark_used(self) -> None:
        """
        标记已使用：
        - 设置 is_used=True，记录 verified_at 时间，然后保存指定字段。
        """
        self.is_used = True
        self.verified_at = timezone.now()
        self.save(update_fields=["is_used", "verified_at", "updated_at"])


class PlayerUser(User):
    """玩家代理模型：复用 User 表，便于后台按类型过滤。"""
    class Meta:
        proxy = True
        verbose_name = "用户"
        verbose_name_plural = "用户"


class StaffUser(User):
    """管理员代理模型：复用 User 表，便于后台按类型过滤。"""
    class Meta:
        proxy = True
        verbose_name = "管理员"
        verbose_name_plural = "管理员"


class MailAccountQuerySet(models.QuerySet):
    """发信账号 QuerySet：封装启用状态与默认账号的获取。"""

    def active(self):
        """返回处于启用状态的账号集合。"""
        return self.filter(is_active=True)

    def get_default(self):
        """
        获取默认发信账号：
        - 优先选择 is_default=True 的启用账号，如无则按优先级取第一个启用账号。
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
    可配置的发信邮箱账户，支持不同服务商。
    """

    class Provider(models.TextChoices):
        QQ = "qq", "QQ 邮箱"
        NETEASE_163 = "163", "163 邮箱"
        GMAIL = "gmail", "Gmail"
        OUTLOOK = "outlook", "Outlook / Office365"
        CUSTOM = "custom", "自定义 SMTP"

    # 服务商类型，用于预设 SMTP 配置
    provider = models.CharField(
        max_length=20,
        choices=Provider.choices,
        default=Provider.QQ,
    )
    # 后台展示名称，便于区分不同账号
    name = models.CharField(max_length=50, help_text="后台展示用名称，便于区分")
    # SMTP 主机地址
    host = models.CharField(max_length=120, blank=True)
    # SMTP 端口
    port = models.PositiveIntegerField(default=587)
    # 是否启用 TLS
    use_tls = models.BooleanField(default=True)
    # 是否启用 SSL
    use_ssl = models.BooleanField(default=False)
    # 登录用户名（邮箱账号）
    username = models.EmailField(help_text="邮箱账号")
    # 授权码或应用专用密码
    password = models.CharField(max_length=255, help_text="授权码或应用专用密码")
    # 发信人显示名称
    from_name = models.CharField(max_length=100, blank=True, help_text="展示名，如 FindTheCat 赛事组委会")
    # 发信邮箱（默认等于用户名）
    from_email = models.EmailField(blank=True, help_text="用于 From 的邮箱地址，默认等于 username")
    # 优先级：数字越小越优先
    priority = models.PositiveIntegerField(default=100, help_text="数字越小优先级越高")
    # 是否启用该发信账号
    is_active = models.BooleanField(default=True)
    # 是否默认账号，设为 True 时其它账号自动取消默认
    is_default = models.BooleanField(default=False, help_text="设为 True 后其余账号将自动取消默认")
    # 创建时间
    created_at = models.DateTimeField(auto_now_add=True)
    # 更新时间
    updated_at = models.DateTimeField(auto_now=True)

    # 基于自定义 QuerySet，提供 active() 能力
    objects = MailAccountQuerySet.as_manager()

    class Meta:
        ordering = ["priority", "-updated_at"]
        verbose_name = "发信账号"
        verbose_name_plural = "发信账号"

    # 常用服务商的默认 SMTP 配置，便于自动填充
    PROVIDER_DEFAULTS = {
        Provider.QQ: {"host": "smtp.qq.com", "port": 587, "use_tls": True, "use_ssl": False},
        Provider.NETEASE_163: {"host": "smtp.163.com", "port": 465, "use_tls": False, "use_ssl": True},
        Provider.GMAIL: {"host": "smtp.gmail.com", "port": 587, "use_tls": True, "use_ssl": False},
        Provider.OUTLOOK: {"host": "smtp.office365.com", "port": 587, "use_tls": True, "use_ssl": False},
    }

    def apply_provider_defaults(self):
        """
        根据服务商填充默认 SMTP 配置：
        - 若 host/port/use_tls/use_ssl 未显式配置，则沿用预设值。
        - CUSTOM 类型不做处理，需手动填写。
        """
        # 获取当前 provider 对应的默认配置
        config = self.PROVIDER_DEFAULTS.get(self.provider)
        if not config:
            return
        # 未填写 host 时使用默认主机
        if not self.host:
            self.host = config["host"]
        # 端口未设置或为 0 时使用默认端口
        if self.port in (0, None):
            self.port = config["port"]
        # TLS/SSL 若为 None 则继承默认布尔值
        if self.use_tls is None:
            self.use_tls = config["use_tls"]
        if self.use_ssl is None:
            self.use_ssl = config["use_ssl"]

    def save(self, *args, **kwargs):
        """
        保存发信账号的预处理：
        - 先应用服务商默认配置，确保必要字段存在。
        - 若未指定发信邮箱，则回填为用户名。
        - 持久化后若为默认账号，取消其他账号的默认标记，保证唯一默认。
        """
        # 应用服务商默认配置，补齐主机/端口/TLS/SSL
        self.apply_provider_defaults()
        # 若未设置 from_email，则使用用户名作为发信邮箱
        if not self.from_email:
            self.from_email = self.username
        # 确保只存在一个默认账号
        super().save(*args, **kwargs)
        if self.is_default:
            MailAccount.objects.exclude(pk=self.pk).update(is_default=False)

    @property
    def from_display(self) -> str:
        """
        构造邮件 From 展示值：
        - 若配置了显示名，则返回 “名称 <邮箱>”。
        - 否则仅返回邮箱地址。
        """
        if self.from_name:
            return f"{self.from_name} <{self.from_email}>"
        return self.from_email
