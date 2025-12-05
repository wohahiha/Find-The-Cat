"""
账户相关模型定义（用户、邮件验证码、邮件账号等）

- 扩展 User 模型（昵称、头像、组织、账号类型等）并覆写 Manager 限制超管数量，满足安全与资料需求
- 邮件验证码模型支持注册/重置密码/绑定邮箱等场景，内置过期与已使用标记
- 邮件账号模型封装 SMTP 配置、默认账号切换与优先级，支撑统一邮件发送基础设施
"""

from __future__ import annotations

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from apps.common.exceptions import AccountIdLimitError


class FTCUserManager(UserManager):
    """
    自定义用户管理器：
    - 业务场景：创建超级管理员时限制数量，避免超管过多带来风险
    - 模块角色：为 User 模型提供带业务约束的创建入口
    - 功能：创建超管时补齐账号类型/管理员标记，超出上限直接拒绝
    """

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        """
        创建超管：附带数量上限校验与默认权限标志

        超级管理员限制：
        - 数量上限：10 个（对应 account_id 1-10）
        - 创建方式：仅允许通过命令行 `python manage.py createsuperuser` 创建
        - 安全考虑：限制高权限账号数量，降低安全风险
        """
        if self.filter(is_superuser=True).count() >= 10:
            raise AccountIdLimitError("超级管理员数量已达上限（10个），无法创建新的超级管理员")
        extra_fields.setdefault("account_type", self.model.AccountType.ADMIN)
        extra_fields.setdefault("is_staff", True)
        return super().create_superuser(username, email=email, password=password, **extra_fields)


class User(AbstractUser):
    """
    FTC 自定义用户模型：
    - 业务场景：承载选手与管理员的认证主体，存储扩展资料
    - 模块角色：被认证、权限、业务服务和邮件发送广泛引用
    - 功能：增加昵称、头像、组织等字段；账号类型标记用户/管理员；保存时自动填充昵称
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
    account_type = models.CharField("账号类型", max_length=10, choices=AccountType.choices, default=AccountType.USER,
                                    db_index=True)
    account_id = models.PositiveIntegerField(
        "ID",
        unique=True,
        null=True,  # 允许为空，方便数据迁移
        blank=True,
        db_index=True,
        help_text="账户ID：1-10超管，11-1000管理员，1001+普通用户"
    )

    objects = FTCUserManager()

    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["email"]

    class Meta(AbstractUser.Meta):  # type: ignore[misc]
        ordering = ["-date_joined"]
        verbose_name = "用户"
        verbose_name_plural = "用户"

    def save(self, *args, **kwargs):
        """
        保存前自动处理：
        1. 自动补充昵称（避免空昵称影响展示）
        2. 自动分配 account_id（如果尚未分配）
        """
        # 1. 自动补充昵称
        if not self.nickname:
            self.nickname = self.username

        # 2. 自动分配 account_id（仅在创建新用户且 account_id 为空时）
        if self.account_id is None:
            self.account_id = self._assign_account_id()

        super().save(*args, **kwargs)

    def _assign_account_id(self) -> int:
        """
        根据用户角色自动分配 account_id

        分配规则：
        - 超级管理员（is_superuser=True）：1-10（最多10个，自动复用缺口）
        - 普通管理员（is_staff=True, is_superuser=False）：11-1000（最多990个，自动复用缺口）
        - 普通用户（is_staff=False）：1001-∞（无限制，按最大值递增）

        Returns:
            分配的 account_id

        Raises:
            AccountIdLimitError: 超管或管理员数量达到上限
        """
        if self.is_superuser:
            # 超管区间（1-10）逐个查找缺口，确保删除旧账号后可以复用编号
            return self._find_available_account_id(1, 10, role_label="超级管理员")

        if self.is_staff:
            # 管理员区间（11-1000）支持自动复用缺口，只有全部占满才会阻止创建
            return self._find_available_account_id(11, 1000, role_label="管理员")

        # 普通用户区间（1001+）不设硬性上限，沿用最大值递增
        max_id = (
            User.objects.filter(account_id__gte=1001)
            .aggregate(models.Max("account_id"))
            .get("account_id__max")
            or 1000
        )
        return max_id + 1

    @staticmethod
    def _find_available_account_id(start: int, end: int, *, role_label: str) -> int:
        """
        查找指定区间内可用的 account_id （复用缺口）

        处理流程：
        1. 拉取区间内所有已占用 ID，并按升序遍历
        2. 找到第一个缺失的数字直接返回，实现“真实占满才到上限”
        3. 若遍历结束且期望值仍在区间内，说明尾部未满，可直接使用
        4. 区间被完全占满时抛出 AccountIdLimitError
        """
        existing_ids = list(
            User.objects.filter(account_id__gte=start, account_id__lte=end)
            .order_by("account_id")
            .values_list("account_id", flat=True)
        )

        expected = start
        for current in existing_ids:
            if current != expected:
                return expected
            expected += 1

        if expected <= end:
            return expected

        raise AccountIdLimitError(f"{role_label}数量已达上限（{start}-{end}），无法创建新的{role_label}")

    @property
    def display_name(self) -> str:
        """展示名：优先昵称，否则回退用户名"""
        return self.nickname or self.username


# 注意：EmailVerificationCode 模型已迁移至 apps.system.models
# 如需使用邮箱验证码，请从 apps.system.models 导入：
# from apps.system.models import EmailVerificationCode


class PlayerUser(User):
    """选手代理模型：复用 User 表，便于在管理端按角色区分"""

    class Meta:
        proxy = True
        verbose_name = "用户"
        verbose_name_plural = "用户"


class StaffUser(User):
    """管理员代理模型：复用 User 表，在管理端聚焦管理员列表"""

    class Meta:
        proxy = True
        verbose_name = "管理员"
        verbose_name_plural = "管理员"


# 注意：MailAccount 模型已迁移至 apps.system.models
# 如需使用发信账号，请从 apps.system.models 导入：
# from apps.system.models import MailAccount
