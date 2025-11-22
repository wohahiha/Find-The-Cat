"""账户模块的数据访问层。

封装 User 与 EmailVerificationCode 的查询、创建、校验等操作，避免视图/服务直接操作 ORM。
"""

from __future__ import annotations

from typing import Optional
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.common.base.base_repo import BaseRepo
from apps.common.exceptions import ValidationError, NotFoundError

from .utils import assign_default_admin_permissions, assign_default_user_permissions

from .models import EmailVerificationCode

User = get_user_model()


class UserRepo(BaseRepo[User]):
    """
    用户仓储：统一封装常用查询与写操作。
    """

    model = User

    def username_exists(self, username: str) -> bool:
        """
        判断用户名是否已存在。
        - username: 待校验的用户名（登录名）。
        """
        return self.filter(username=username).exists()

    def email_exists(self, email: str) -> bool:
        """
        判断邮箱是否已存在。
        - email: 待校验的邮箱；用于注册唯一性检查。
        """
        return self.filter(email=email).exists()

    def email_exists_for_other(self, email: str, *, exclude_user_id: int) -> bool:
        """
        判断邮箱是否被除指定用户外的其他账号占用。
        - email: 待校验的邮箱。
        - exclude_user_id: 需要排除的用户主键（用于个人资料修改时的唯一性校验）。
        """
        return self.filter(email=email).exclude(pk=exclude_user_id).exists()

    def get_by_email(self, email: str) -> User:
        """
        根据邮箱获取用户，如不存在则抛业务级 NotFoundError。
        - email: 目标邮箱。
        """
        try:
            return self.filter(email=email).get()
        except User.DoesNotExist as exc:  # type: ignore[attr-defined]
            raise NotFoundError(message="用户不存在") from exc

    def get_by_identifier(self, identifier: str) -> Optional[User]:
        """
        根据用户名或邮箱获取用户。
        - identifier: 输入标识，可为用户名或邮箱（通过是否包含 @ 判断）。
        """
        # 根据是否包含 @ 选择邮箱或用户名查询，保证登录时两种方式兼容
        qs = self.get_queryset()
        lookup = {"email": identifier} if "@" in identifier else {"username": identifier}
        return qs.filter(**lookup).first()

    def create_user(self, *, username: str, email: str, password: str, **extra) -> User:
        """
        创建用户（普通或管理员），并按账号类型分配默认权限。
        - username/email/password: 基础注册信息。
        - extra: 额外字段（如 account_type、昵称等）。
        """
        # 使用 Django 内置 create_user，自动处理密码哈希
        user: User = self.model.objects.create_user(  # type: ignore[call-arg]
            username=username,
            email=email,
            password=password,
            **extra,
        )
        # 按账号类型分配权限组：管理员→默认管理员权限，普通用户→默认用户权限
        if user.account_type == User.AccountType.ADMIN or user.is_staff:
            assign_default_admin_permissions(user)
        else:
            assign_default_user_permissions(user)
        return user

    def set_password(self, user: User, new_password: str) -> User:
        """
        重置密码并持久化。
        - user: 目标用户。
        - new_password: 新密码明文（内部会做哈希）。
        """
        # 调用 Django 提供的 set_password 进行哈希存储
        user.set_password(new_password)
        # 仅更新密码与更新时间字段，避免覆盖其他字段
        user.save(update_fields=["password", "updated_at"])
        return user

    def mark_email_verified(self, user: User) -> None:
        """
        将用户邮箱标记为已验证。
        - user: 目标用户。
        """
        # 避免重复写库，只有未验证时才更新
        if not user.is_email_verified:
            user.is_email_verified = True
            user.save(update_fields=["is_email_verified", "updated_at"])


class EmailVerificationCodeRepo(BaseRepo[EmailVerificationCode]):
    """
    邮箱验证码仓储。
    """

    model = EmailVerificationCode

    def create_code(
        self,
        *,
        email: str,
        scene: str,
        code: str,
        expires_at,
    ) -> EmailVerificationCode:
        """
        创建验证码记录。
        - email: 接收验证码的邮箱。
        - scene: 业务场景（注册/重置密码/绑定邮箱）。
        - code: 验证码内容。
        - expires_at: 过期时间。
        """
        return self.create(
            {
                "email": email,
                "scene": scene,
                "code": code,
                "expires_at": expires_at,
            }
        )

    def latest(self, *, email: str, scene: str) -> Optional[EmailVerificationCode]:
        """
        获取邮箱在指定场景下的最新验证码记录。
        - email: 目标邮箱。
        - scene: 场景标识。
        """
        return (
            self.filter(email=email, scene=scene)
            .order_by("-created_at")
            .first()
        )

    def consume(self, *, email: str, scene: str, code: str) -> EmailVerificationCode:
        """
        校验并消费验证码：
        - email/scene/code: 校验条件，按最新记录优先。
        - 业务规则：不存在/已用/过期均抛 ValidationError，否则标记已用。
        """
        # 按时间倒序取最新的匹配记录
        record = (
            self.filter(email=email, scene=scene, code=code)
            .order_by("-created_at")
            .first()
        )
        # 不存在：验证码错误或已失效
        if record is None:
            raise ValidationError(message="验证码错误或已失效")

        # 已使用：阻止重复消费
        if record.is_used:
            raise ValidationError(message="验证码已被使用")

        # 已过期：阻止使用超时验证码
        if record.is_expired:
            raise ValidationError(message="验证码已过期")

        # 通过校验：标记已使用并返回记录
        record.mark_used()
        return record

    def has_recent_code(self, *, email: str, scene: str, seconds: int) -> bool:
        """
        判断最近 seconds 秒内是否已经发送过验证码。
        - email: 目标邮箱。
        - scene: 业务场景。
        - seconds: 时间窗口（秒），用于防刷/限流。
        """
        # 计算时间阈值：当前时间减去窗口秒数
        threshold = timezone.now() - timedelta(seconds=seconds)
        # 在时间窗口内是否存在相同邮箱+场景的验证码
        return (
            self.filter(email=email, scene=scene, created_at__gte=threshold)
            .exists()
        )
