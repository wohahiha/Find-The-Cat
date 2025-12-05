"""账户模块的数据访问层

封装 User 与 EmailVerificationCode 的查询、创建、校验等操作，避免视图/服务直接操作 ORM
"""

from __future__ import annotations

from typing import Optional
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.common.base.base_repo import BaseRepo
from apps.common.exceptions import ValidationError, NotFoundError, RateLimitError, CacheUnavailableError
from apps.common.infra import redis_client
from apps.common.utils import redis_keys

from .utils import assign_default_admin_permissions, assign_default_user_permissions

# EmailVerificationCode 已迁移至 system 模块
from apps.system.models import EmailVerificationCode

User = get_user_model()


class UserRepo(BaseRepo[User]):
    """
    用户仓储：
    - 业务场景：注册、登录、修改资料/密码/邮箱等需要读写用户
    - 模块角色：封装 User 常用查询与写操作，避免业务层散落 ORM 逻辑
    - 功能：唯一性校验、标记邮箱验证、创建用户并分配默认权限等
    """

    model = User

    def username_exists(self, username: str) -> bool:
        """
        判断用户名是否已存在
        - 业务：注册时唯一性校验
        - 参数 username：待校验的用户名
        """
        return self.filter(username=username).exists()

    def email_exists(self, email: str) -> bool:
        """
        判断邮箱是否已存在
        - 业务：注册时唯一性校验
        - 参数 email：待校验的邮箱
        """
        return self.filter(email=email).exists()

    def email_exists_for_other(self, email: str, *, exclude_user_id: int) -> bool:
        """
        判断邮箱是否被除指定用户外的其他账号占用
        - 业务：修改邮箱时的唯一性校验
        - 参数 email：待校验的邮箱；exclude_user_id：排除当前用户
        """
        return self.filter(email=email).exclude(pk=exclude_user_id).exists()

    def get_by_email(self, email: str) -> User:
        """
        根据邮箱获取用户，不存在抛 NotFoundError
        - 业务：重置密码、邮箱验证等需要按邮箱定位用户
        - 参数 email：目标邮箱
        """
        try:
            return self.filter(email=email).get()
        except User.DoesNotExist as exc:  # type: ignore[attr-defined]
            raise NotFoundError(message="用户不存在") from exc

    def get_by_identifier(self, identifier: str) -> Optional[User]:
        """
        根据用户名或邮箱获取用户
        - 业务：登录时兼容用户名/邮箱两种方式
        - 参数 identifier：用户名或邮箱，通过是否包含 @ 选择查询字段
        """
        # 根据是否包含 @ 选择邮箱或用户名查询，保证登录时两种方式兼容
        qs = self.get_queryset()
        lookup = {"email": identifier} if "@" in identifier else {"username": identifier}
        return qs.filter(**lookup).first()

    def create_user(self, *, username: str, email: str, password: str, **extra) -> User:
        """
        创建用户（普通或管理员），并按账号类型分配默认权限
        - 业务：注册或后台创建用户
        - 参数 username/email/password：基础注册信息；extra：账号类型/昵称等
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

    @staticmethod
    def set_password(user: User, new_password: str) -> User:
        """
        重置密码并持久化
        - 业务：重置/修改密码
        - 参数 user：目标用户；new_password：新密码明文（内部做哈希）
        """
        # 调用 Django 提供的 set_password 进行哈希存储
        user.set_password(new_password)
        # 仅更新密码与更新时间字段，避免覆盖其他字段
        user.save(update_fields=["password", "updated_at"])
        return user

    @staticmethod
    def mark_email_verified(user: User) -> None:
        """
        将用户邮箱标记为已验证
        - 业务：注册/绑定邮箱成功后更新状态
        - 参数 user：目标用户
        """
        # 避免重复写库，只有未验证时才更新
        if not user.is_email_verified:
            user.is_email_verified = True
            user.save(update_fields=["is_email_verified", "updated_at"])

    @staticmethod
    def update_avatar(user: User, avatar_url: str) -> User:
        """
        更新用户头像地址
        - 业务：用户/管理员上传头像后写入 URL
        - 参数 user：目标用户；avatar_url：头像访问 URL 或相对路径
        """
        user.avatar = avatar_url
        user.save(update_fields=["avatar", "updated_at"])
        return user


class EmailVerificationCodeRepo(BaseRepo[EmailVerificationCode]):
    """
    邮箱验证码仓储：
    - 业务场景：发送/校验/消费验证码
    - 模块角色：集中管理验证码的创建、查询与消费规则
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
        创建验证码记录
        - 业务：发送验证码时落库
        - 参数 email：目标邮箱；scene：业务场景；code：验证码；expires_at：过期时间
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
        获取邮箱在指定场景下的最新验证码记录
        - 业务：校验/限流时取最近一次发送
        - 参数 email：目标邮箱；scene：场景标识
        """
        return (
            self.filter(email=email, scene=scene)
            .order_by("-created_at")
            .first()
        )

    def consume(self, *, email: str, scene: str, code: str) -> EmailVerificationCode:
        """
        校验并消费验证码：
        - email/scene/code: 校验条件，按最新记录优先
        - 业务规则：不存在/已用/过期均抛 ValidationError，否则标记已用
        """
        # 校验错误次数风控：同邮箱+场景错误超过阈值暂时阻断
        fail_key = redis_keys.email_code_fail_key(email, scene)
        max_fail = 5
        block_seconds = 300
        try:
            current_fail = redis_client.get(fail_key)
            if current_fail is not None and int(current_fail) >= max_fail:
                raise RateLimitError(message="验证码错误次数过多，请稍后再试")
        except (ValueError, CacheUnavailableError):
            # Redis 不可用或值异常时忽略，走后续校验
            pass

        # 按时间倒序取最新的匹配记录
        record = (
            self.filter(email=email, scene=scene, code=code)
            .order_by("-created_at")
            .first()
        )
        # 不存在：验证码错误或已失效
        if record is None:
            try:
                new_fail = redis_client.incr(fail_key, ex=block_seconds)
                if new_fail >= max_fail:
                    raise RateLimitError(message="验证码错误次数过多，请稍后再试")
            except CacheUnavailableError:
                pass
            raise ValidationError(message="验证码错误或已失效")

        # 已使用：阻止重复消费
        if record.is_used:
            try:
                new_fail = redis_client.incr(fail_key, ex=block_seconds)
                if new_fail >= max_fail:
                    raise RateLimitError(message="验证码错误次数过多，请稍后再试")
            except CacheUnavailableError:
                pass
            raise ValidationError(message="验证码已被使用")

        # 已过期：阻止使用超时验证码
        if record.is_expired:
            try:
                new_fail = redis_client.incr(fail_key, ex=block_seconds)
                if new_fail >= max_fail:
                    raise RateLimitError(message="验证码错误次数过多，请稍后再试")
            except CacheUnavailableError:
                pass
            raise ValidationError(message="验证码已过期")

        # 通过校验：标记已使用并返回记录
        record.mark_used()
        # 成功后清空失败计数
        try:
            redis_client.delete(fail_key)
        except CacheUnavailableError:
            pass
        return record

    def has_recent_code(self, *, email: str, scene: str, seconds: int) -> bool:
        """
        判断最近 seconds 秒内是否已经发送过验证码
        - 业务：限流，防止重复发送
        - 参数 email：目标邮箱；scene：业务场景；seconds：时间窗口（秒）
        """
        # 计算时间阈值：当前时间减去窗口秒数
        threshold = timezone.now() - timedelta(seconds=seconds)
        # 在时间窗口内是否存在相同邮箱+场景的验证码
        return (
            self.filter(email=email, scene=scene, created_at__gte=threshold)
            .exists()
        )
