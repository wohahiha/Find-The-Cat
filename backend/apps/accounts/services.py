"""账户模块的业务服务层

职责：
- 发送/校验邮箱验证码（注册、找回密码、换绑邮箱）
- 用户注册、登录（JWT）、重置密码、修改资料/邮箱/密码、注销账号
- 统一封装业务流程与异常抛出，视图层仅做参数接收与结果返回
"""

from __future__ import annotations
import secrets
import mimetypes
from datetime import timedelta
from uuid import uuid4
from pathlib import Path

from django.utils import timezone
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
from captcha.models import CaptchaStore

from apps.common.base.base_service import BaseService
from apps.common.exceptions import (
    ConflictError,
    RateLimitError,
    NotFoundError,
    InvalidCredentialsError,
    AccountInactiveError,
    CaptchaValidationError,
    EmailNotVerifiedError,
    EmailSendError,
    BizError,
)

from django.template.loader import render_to_string
from apps.common.infra.email_sender import send_mail_with_account, send_mail_with_settings
from apps.common.infra.logger import get_logger, logger_extra
from apps.common.infra.file_storage import default_storage

# EmailVerificationCode 已迁移至 system 模块
from .models import User
from apps.system.models import EmailVerificationCode
from .repo import UserRepo, EmailVerificationCodeRepo
# MailAccount 已迁移至系统模块
from apps.system.models import MailAccount
from .schemas import (
    SendEmailCodeSchema,
    RegisterSchema,
    LoginSchema,
    ResetPasswordSchema,
    ProfileUpdateSchema,
    ChangePasswordSchema,
    ChangeEmailSchema,
    DeleteAccountSchema,
    AvatarUploadSchema,
)
from apps.common.permission_sets import iter_permission_labels
from .utils import assign_default_user_permissions

logger = get_logger(__name__)


def serialize_user(user: User) -> dict[str, object]:
    """
    用户序列化工具：将 User 模型转换为 API 输出字典
    - 业务场景：登录/注册/资料更新等接口返回用户信息时统一格式
    - 模块角色：轻量级 Presenter，避免视图重复拼装字段
    - 参数 user：要序列化的用户实例；返回包含基础资料、权限标志与时间字段
    """
    return {
        "id": user.pk,
        "username": user.username,
        "nickname": user.nickname,
        "email": user.email,
        "avatar": user.avatar,
        "bio": user.bio,
        "organization": user.organization,
        "country": user.country,
        "website": user.website,
        "is_email_verified": user.is_email_verified,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "date_joined": user.date_joined.isoformat() if user.date_joined else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        # 权限概览：转成简短中文标签，便于前端展示权限概况
        "permissions": iter_permission_labels(user.get_all_permissions()),
        # 角色列表：方便前端展示/编辑
        "roles": [
            {
                "id": g.id,
                "name": g.name,
                "is_builtin": g.name in {"Admins::Default", "Users::Default"},
            }
            for g in user.groups.all().order_by("name")
        ],
    }


class SendEmailVerificationService(BaseService[EmailVerificationCode]):
    """
    发送邮箱验证码服务：
    - 业务场景：注册、找回密码、绑定/变更邮箱
    - 职责：校验频率、生成验证码、落库并发送邮件
    - 输出：创建的验证码记录
    """

    code_ttl = timedelta(minutes=10)
    cooldown_seconds = 60

    def __init__(
            self,
            user_repo: UserRepo | None = None,
            code_repo: EmailVerificationCodeRepo | None = None,
            mail_account: MailAccount | None = None,
    ):
        # 用户仓储：用于邮箱存在性校验
        self.user_repo = user_repo or UserRepo()
        # 验证码仓储：用于限流、创建、消费
        self.code_repo = code_repo or EmailVerificationCodeRepo()
        # 发信账号：若未指定则取默认发信配置
        self.mail_account = mail_account or MailAccount.objects.get_default()
        # 动态验证码有效期：可由后台配置覆盖，默认 10 分钟
        expire_minutes = 10
        if self.mail_account and getattr(self.mail_account, "verification_expire_minutes", None):
            try:
                expire_minutes = int(self.mail_account.verification_expire_minutes)
            except Exception:
                expire_minutes = 10
        # 加上下界，避免过短/过长导致风控或弱安全
        expire_minutes = max(5, min(expire_minutes, 30))
        self.expire_minutes = expire_minutes
        self.code_ttl = timedelta(minutes=expire_minutes)

    @staticmethod
    def _generate_code() -> str:
        """生成 6 位纯数字验证码"""
        return "".join(secrets.choice("0123456789") for _ in range(6))

    def _deliver(self, email: str, scene: str, code: str) -> None:
        """
        发送验证码邮件：
        - email: 目标邮箱
        - scene: 验证码场景，用于文案映射
        - code: 验证码内容
        """
        subject = "您的验证码"
        scene_map = {
            EmailVerificationCode.Scene.REGISTER: "注册账号",
            EmailVerificationCode.Scene.RESET_PASSWORD: "找回密码",
            EmailVerificationCode.Scene.BIND_EMAIL: "绑定邮箱",
            EmailVerificationCode.Scene.CHANGE_PASSWORD: "修改密码",
        }
        # 构造邮件正文，包含验证码与有效期提示
        body = (
            f"您正在进行 {scene_map.get(scene, '操作')}，验证码为 {code}，"
            f"{self.expire_minutes} 分钟内有效。如果不是您本人操作，请忽略此邮件"
        )
        # 构造 HTML 正文，便于自定义品牌
        brand = ""
        support_email = ""
        site_url = ""
        logo_cid = ""
        inline_images: list[dict[str, object]] = []
        if self.mail_account:
            brand = self.mail_account.from_name or self.mail_account.username or ""
            support_email = self.mail_account.support_email or self.mail_account.username or ""
            site_url = self.mail_account.site_url or ""
            if self.mail_account.logo:
                try:
                    logo_cid = f"logo-{self.mail_account.pk or 'default'}"
                    mime_type, _ = mimetypes.guess_type(self.mail_account.logo.name)
                    mime_type = mime_type or "image/png"
                    with self.mail_account.logo.open("rb") as logo_file:
                        inline_images.append(
                            {
                                "cid": logo_cid,
                                "content": logo_file.read(),
                                "mimetype": mime_type,
                            }
                        )
                except FileNotFoundError:
                    logger.warning(
                        "邮箱 Logo 文件不存在，跳过内联",
                        extra=logger_extra({"account_id": getattr(self.mail_account, "id", None)}),
                    )
                except Exception:
                    logger.exception(
                        "读取邮箱 Logo 失败",
                        extra=logger_extra({"account_id": getattr(self.mail_account, "id", None)}),
                    )
            if getattr(self.mail_account, "verification_subject", None):
                subject = self.mail_account.verification_subject or subject
        html_body = render_to_string(
            "emails/verification_code.html",
            {
                "brand": brand,
                "code": code,
                "expire_minutes": self.expire_minutes,
                "scene": scene_map.get(scene, "操作"),
                "support_email": support_email,
                "site_url": site_url,
                "logo_cid": logo_cid,
            },
        )
        try:
            # 优先使用指定/默认的发信账号
            if self.mail_account:
                send_mail_with_account(
                    account=self.mail_account,
                    subject=subject,
                    body=body,
                    html_body=html_body,
                    inline_images=inline_images,
                    to=[email],
                )
            else:
                # 无专用账号时回退到 settings 邮件配置
                send_mail_with_settings(
                    subject=subject,
                    body=body,
                    html_body=html_body,
                    inline_images=inline_images,
                    to=[email],
                )
        except BizError:
            # 业务异常（如收件邮箱无效）直接透传，便于前端获得具体原因
            raise
        except Exception as exc:
            logger.exception(
                "发送验证码邮件失败",
                extra=logger_extra({"email": email, "scene": scene}),
            )
            raise EmailSendError() from exc

    def perform(self, schema: SendEmailCodeSchema) -> EmailVerificationCode:
        """
        发送验证码主流程：
        - 校验邮箱是否可用（注册/重置流的存在性要求）
        - 限流：60 秒内同场景同邮箱不可重复发送
        - 生成并存储验证码，触发邮件发送
        """
        # 邮箱统一小写，场景直接取 schema
        email = schema.email.lower()
        scene = schema.scene

        # 注册场景要求：邮箱未被注册
        if scene == EmailVerificationCode.Scene.REGISTER and self.user_repo.email_exists(email):
            raise ConflictError(message="该邮箱已注册账户")
        # 重置密码场景要求：邮箱必须存在且已完成验证
        if scene == EmailVerificationCode.Scene.RESET_PASSWORD:
            user = self.user_repo.get_queryset().filter(email=email).first()
            if not user:
                raise NotFoundError(message="账号不存在")
            if not user.is_email_verified:
                raise EmailNotVerifiedError(message="邮箱未验证，无法重置密码")
        # 修改密码场景：要求邮箱存在且已验证
        if scene == EmailVerificationCode.Scene.CHANGE_PASSWORD:
            user = self.user_repo.get_queryset().filter(email=email).first()
            if not user:
                raise NotFoundError(message="账号不存在")
            if not user.is_email_verified:
                raise EmailNotVerifiedError(message="邮箱未验证，无法发送验证码")

        # 限流：指定窗口内已有验证码则拒绝
        if self.code_repo.has_recent_code(email=email, scene=scene, seconds=self.cooldown_seconds):
            raise RateLimitError(message="验证码发送过于频繁，请稍后再试")

        # 生成验证码并计算过期时间
        code = self._generate_code()
        expires_at = timezone.now() + self.code_ttl
        # 写入数据库记录
        record = self.code_repo.create_code(
            email=email,
            scene=scene,
            code=code,
            expires_at=expires_at,
        )

        # 发送邮件，异常已在内部记录日志
        self._deliver(email=email, scene=scene, code=code)
        logger.info(
            "发送邮箱验证码",
            extra=logger_extra({"email": email, "scene": scene}),
        )
        return record


class RegisterService(BaseService[User]):
    """
    选手注册服务：
    - 校验用户名/邮箱唯一性
    - 校验注册邮箱验证码
    - 创建用户并分配默认权限组，标记邮箱验证通过
    """

    def __init__(
            self,
            user_repo: UserRepo | None = None,
            code_repo: EmailVerificationCodeRepo | None = None,
    ):
        # 用户仓储：唯一性校验与创建
        self.user_repo = user_repo or UserRepo()
        # 验证码仓储：校验注册验证码
        self.code_repo = code_repo or EmailVerificationCodeRepo()

    def perform(self, schema: RegisterSchema) -> User:
        """
        注册主流程：
        - 校验用户名/邮箱是否占用
        - 消费注册验证码
        - 创建用户并默认验证邮箱
        """
        email = schema.email.lower()
        username = schema.username

        # 唯一性校验：用户名和邮箱不得重复
        if self.user_repo.username_exists(username):
            raise ConflictError(message="用户名已被使用")
        if self.user_repo.email_exists(email):
            raise ConflictError(message="邮箱已注册账号")

        # 校验并消费注册验证码
        self.code_repo.consume(email=email, scene=EmailVerificationCode.Scene.REGISTER, code=schema.email_code)

        # 生成昵称（默认使用用户名）
        nickname = schema.nickname or username
        # 创建用户记录
        user = self.user_repo.create_user(
            username=username,
            email=email,
            password=schema.password,
            nickname=nickname,
        )
        # 标记邮箱已验证
        self.user_repo.mark_email_verified(user)
        # 兜底分配默认用户权限
        assign_default_user_permissions(user)
        logger.info("注册成功", extra=logger_extra({"user_id": user.id, "email": email}))
        return user


class LoginService(BaseService[dict[str, object]]):
    """
    登录服务：
    - 支持用户名或邮箱登录
    - 校验账户状态与密码，返回 JWT 刷新/访问令牌及用户信息
    """

    atomic_enabled = False

    def __init__(self, user_repo: UserRepo | None = None):
        # 用户仓储：用于查找用户
        self.user_repo = user_repo or UserRepo()

    def perform(self, schema: LoginSchema) -> dict[str, object]:
        """
        登录主流程：
        - 根据 identifier 获取用户
        - 校验账户有效性与密码正确性
        - 校验图形验证码
        - 颁发 JWT Refresh 与 Access
        """
        allow_without_captcha = getattr(settings, "ALLOW_LOGIN_WITHOUT_CAPTCHA", False)
        if schema.captcha_key and schema.captcha_code:
            self._verify_captcha(schema.captcha_key, schema.captcha_code)
        elif not allow_without_captcha:
            # 理论上 Schema 已阻止，但此处兜底，防止绕过校验
            raise CaptchaValidationError(message="请完成图形验证码")
        identifier = schema.identifier
        user = self.user_repo.get_by_identifier(identifier)
        if user is None:
            logger.warning(
                "登录失败：账号不存在",
                extra=logger_extra({"identifier": identifier}),
            )
            raise InvalidCredentialsError(message="账号或密码错误")

        if not user.is_active:
            logger.warning(
                "登录失败：账户失效",
                extra=logger_extra({"user_id": getattr(user, 'id', None), "identifier": identifier}),
            )
            raise AccountInactiveError(message="账户失效，请联系管理员")

        if not user.is_email_verified:
            logger.warning(
                "登录失败：邮箱未验证",
                extra=logger_extra({"user_id": getattr(user, 'id', None), "identifier": identifier}),
            )
            raise EmailNotVerifiedError(message="邮箱未验证，请先完成邮箱验证")

        if not user.check_password(schema.password):
            logger.warning(
                "登录失败：密码错误",
                extra=logger_extra({"user_id": getattr(user, 'id', None), "identifier": identifier}),
            )
            raise InvalidCredentialsError(message="账号或密码错误")

        refresh = RefreshToken.for_user(user)
        logger.info(
            "登录成功",
            extra=logger_extra({"user_id": user.id, "identifier": identifier}),
        )
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": serialize_user(user),
        }

    @staticmethod
    def _verify_captcha(key: str, code: str) -> None:
        """校验图形验证码，错误时抛出业务异常"""
        store = CaptchaStore.objects.filter(hashkey=key).first()
        if not store:
            raise CaptchaValidationError(message="验证码已失效，请刷新后重试")
        # 验证后立即删除，避免重放
        CaptchaStore.objects.filter(pk=store.pk).delete()
        if store.response.lower() != code.lower():
            raise CaptchaValidationError(message="验证码错误，请刷新后重试")


class ResetPasswordService(BaseService[User]):
    """
    通过邮箱验证码重置密码：
    - 校验验证码后重置目标邮箱对应用户的密码
    """

    def __init__(
            self,
            user_repo: UserRepo | None = None,
            code_repo: EmailVerificationCodeRepo | None = None,
    ):
        # 用户仓储：用于查询/写入用户
        self.user_repo = user_repo or UserRepo()
        # 验证码仓储：用于消费重置验证码
        self.code_repo = code_repo or EmailVerificationCodeRepo()

    def perform(self, schema: ResetPasswordSchema) -> User:
        """
        重置密码主流程：
        - 消费重置场景的验证码
        - 获取用户并设置新密码
        """
        email = schema.email.lower()
        self.code_repo.consume(email=email, scene=EmailVerificationCode.Scene.RESET_PASSWORD, code=schema.code)
        user = self.user_repo.get_by_email(email)
        if not user.is_email_verified:
            raise EmailNotVerifiedError(message="邮箱未验证，无法重置密码")
        user = self.user_repo.set_password(user, schema.new_password)
        logger.info(
            "重置密码成功",
            extra=logger_extra({"user_id": user.id, "email": email}),
        )
        return user


class UpdateProfileService(BaseService[User]):
    """
    更新个人资料：
    - 支持部分字段更新，并记录更新时间
    """

    def perform(self, user: User, schema: ProfileUpdateSchema) -> User:
        """
        资料更新流程：
        - 根据 schema 提取非空字段并逐项覆盖用户属性
        - 保存时仅更新修改字段与更新时间，减少数据库写入
        """
        payload = schema.to_dict(exclude_none=True)
        # 将有效字段写回用户对象
        for field, value in payload.items():
            setattr(user, field, value)
        # 仅保存修改过的字段 + 更新时间
        user.save(update_fields=[*payload.keys(), "updated_at"])
        return user


class ChangePasswordService(BaseService[User]):
    """
    登录态下修改密码：
    - 需要旧密码验证身份 + 邮箱验证码，再设置新密码
    """

    def __init__(
            self,
            user_repo: UserRepo | None = None,
            code_repo: EmailVerificationCodeRepo | None = None,
    ):
        # 用户仓储：用于密码写入
        self.user_repo = user_repo or UserRepo()
        # 验证码仓储：校验修改密码场景验证码
        self.code_repo = code_repo or EmailVerificationCodeRepo()

    def perform(self, user: User, schema: ChangePasswordSchema) -> User:
        """
        修改密码主流程：
        - 校验旧密码正确性与邮箱验证码
        - 写入新密码并返回用户
        """
        if not user.check_password(schema.old_password):
            raise InvalidCredentialsError(message="当前密码不正确")
        # 确保邮箱已验证后再校验验证码
        email = (user.email or "").lower()
        if not email or not user.is_email_verified:
            raise EmailNotVerifiedError(message="邮箱未验证，无法修改密码")
        self.code_repo.consume(
            email=email,
            scene=EmailVerificationCode.Scene.CHANGE_PASSWORD,
            code=schema.email_code,
        )
        user = self.user_repo.set_password(user, schema.new_password)
        logger.info("修改密码成功", extra=logger_extra({"user_id": user.id}))
        return user


class ChangeEmailService(BaseService[User]):
    """
    变更邮箱服务：
    - 需要当前密码验证身份
    - 校验邮箱唯一性与场景验证码
    """

    def __init__(
            self,
            user_repo: UserRepo | None = None,
            code_repo: EmailVerificationCodeRepo | None = None,
    ):
        # 用户仓储：查找/写入用户
        self.user_repo = user_repo or UserRepo()
        # 验证码仓储：校验绑定邮箱验证码
        self.code_repo = code_repo or EmailVerificationCodeRepo()

    def perform(self, user: User, schema: ChangeEmailSchema) -> User:
        """
        变更邮箱主流程：
        - 校验当前密码
        - 校验新邮箱与旧邮箱不同、未被其他账号占用
        - 消费绑定邮箱验证码
        - 更新邮箱并标记已验证
        """
        if not user.check_password(schema.current_password):
            raise InvalidCredentialsError(message="当前密码不正确")

        new_email = schema.new_email.lower()
        if new_email == user.email:
            raise ConflictError(message="新邮箱与当前邮箱相同")
        if self.user_repo.email_exists_for_other(new_email, exclude_user_id=user.pk):
            raise ConflictError(message="该邮箱已绑定其他账号")

        self.code_repo.consume(email=new_email, scene=EmailVerificationCode.Scene.BIND_EMAIL, code=schema.email_code)

        user.email = new_email
        user.is_email_verified = True
        user.save(update_fields=["email", "is_email_verified", "updated_at"])
        logger.info("修改邮箱成功", extra=logger_extra({"user_id": getattr(user, "id", None), "email": new_email}))
        return user


class DeleteAccountService(BaseService[User]):
    """
    注销账号：
    - 校验密码后进行“软删除”处理，释放用户名和邮箱占用
    - 通过改名/改邮箱/禁用账号/清空可识别信息来防止再登录
    """

    def perform(self, user: User, schema: DeleteAccountSchema) -> User:
        """
        注销主流程：
        - 校验密码
        - 生成唯一后缀，重写用户名和邮箱，清空个人信息并禁用账号
        - 设置不可用密码，防止再次登录
        """
        if not user.check_password(schema.password):
            raise InvalidCredentialsError(message="密码不正确，无法注销账号")

        # 生成随机后缀，避免用户名/邮箱冲突
        suffix = uuid4().hex[:8]
        user.username = f"deleted_user_{user.pk}_{suffix}"
        user.email = f"deleted_{user.pk}_{suffix}@deleted.local"
        # 软删除：禁用账号与邮箱验证标志
        user.is_active = False
        user.is_email_verified = False
        # 清空可识别的个人信息
        user.nickname = "已注销用户"
        user.bio = ""
        user.avatar = ""
        user.organization = ""
        user.country = ""
        user.website = ""
        # 设置不可用密码，防止登录
        user.set_unusable_password()
        user.save(
            update_fields=[
                "username",
                "email",
                "is_active",
                "is_email_verified",
                "nickname",
                "bio",
                "avatar",
                "organization",
                "country",
                "website",
                "password",
                "updated_at",
            ]
        )
        logger.info("用户已注销", extra=logger_extra({"user_id": user.pk}))
        # 账户失效后推送强制下线，确保已登录端及时断开
        try:
            from apps.common.ws_utils import broadcast_force_logout

            broadcast_force_logout(user.pk, reason="账号已注销")
        except RuntimeError:
            # WebSocket 推送失败不影响注销流程
            pass
        return user


class AvatarUploadService(BaseService[str]):
    """
    上传头像服务：
    - 校验文件后写入存储并更新用户头像 URL
    """

    def __init__(self, user_repo: UserRepo | None = None):
        # 用户仓储：写入头像地址
        self.user_repo = user_repo or UserRepo()
        # 使用统一存储封装，支持本地/OSS
        self.storage = default_storage

    def perform(self, user: User, schema: AvatarUploadSchema) -> str:
        """
        上传头像主流程：
        - 生成安全文件名并保存到 avatars 子目录
        - 取得可访问 URL（或相对路径）写入用户
        """
        file_obj = schema.file
        original_name = getattr(file_obj, "name", "") or "avatar.png"
        # 取后缀并兜底为 png，避免无后缀文件导致类型混淆
        suffix = Path(original_name).suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
            content_type = getattr(file_obj, "content_type", "") or ""
            suffix_map = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
            suffix = suffix_map.get(content_type, ".png")
        filename = f"avatar_{getattr(user, 'pk', 'u')}_{uuid4().hex}{suffix}"
        content = file_obj.read()
        # 保存文件到统一存储
        relative_path, url = self.storage.save_bytes(content=content, filename=filename, subdir="avatars")
        avatar_url = url or relative_path
        # 写入用户头像
        self.user_repo.update_avatar(user, avatar_url)
        logger.info("上传头像成功", extra=logger_extra({"user_id": getattr(user, "id", None), "avatar": avatar_url}))
        return avatar_url
