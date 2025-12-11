"""账户模块的 API 视图层

每个接口仅负责：
- 接收并校验参数（Schema）
- 调用对应业务 Service
- 使用统一响应封装成功结果
"""

from __future__ import annotations

from django.conf import settings
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiExample
from rest_framework import serializers
from rest_framework import parsers
from captcha.models import CaptchaStore
from captcha.helpers import captcha_image_url
from django.core.cache import cache

from apps.common import response
from apps.common.permissions import IsAuthenticated, AllowAny
from apps.common.throttles import LoginRateThrottle, RegisterRateThrottle, UserPostRateThrottle, EmailCodeSendRateThrottle
from apps.common.security import log_security_event
from apps.common.exceptions import BizError, TokenError, ValidationError
from rest_framework_simplejwt.tokens import RefreshToken
from apps.common.exceptions import RateLimitError, CacheUnavailableError  # noqa: F401
from apps.common.utils import redis_keys
from apps.common.schema_utils import api_response_schema, user_summary_serializer

# EmailVerificationCode 已迁移至 system 模块
from apps.system.models import EmailVerificationCode
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
from .services import (
    SendEmailVerificationService,
    RegisterService,
    LoginService,
    ResetPasswordService,
    UpdateProfileService,
    ChangePasswordService,
    ChangeEmailService,
    DeleteAccountService,
    serialize_user,
    AvatarUploadService,
)


class RolesPlaceholderView(APIView):
    """
    角色列表占位接口
    - 当前返回空列表，后续补充 RBAC
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="获取角色列表（占位）",
        description="获取角色列表（当前返回空列表占位）",
        tags=["accounts-auth"],
        responses=api_response_schema(
            "RolesPlaceholder",
            {"items": serializers.ListField(child=serializers.DictField(), default=[])},
        ),
    )
    def get(self, request: Request) -> Response:
        _ = request
        return response.success({"items": []}, message="角色功能暂未开放")


class PermissionsPlaceholderView(APIView):
    """
    权限列表占位接口
    - 当前返回空列表，后续补充 RBAC
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="获取权限列表（占位）",
        description="获取权限列表（当前返回空列表占位）",
        tags=["accounts-auth"],
        responses=api_response_schema(
            "PermissionsPlaceholder",
            {"items": serializers.ListField(child=serializers.CharField(), default=[])},
        ),
    )
    def get(self, request: Request) -> Response:
        _ = request
        return response.success({"items": []}, message="权限功能暂未开放")


def _set_jwt_cookie(resp: Response, access_token: str) -> None:
    """
    根据配置决定是否写入 JWT Cookie
    - 业务场景：登录成功后可选择把 access token 写入 HttpOnly Cookie，便于前端少操作
    - 参数 resp: DRF Response 对象；access_token: JWT 访问令牌
    """
    # 默认关闭 Cookie 模式；仅在明确需要时开启（例如兼容旧前端）
    if getattr(settings, "JWT_USE_COOKIE", False):
        # Cookie 名称可配置，默认 jwt_token_in_cookie
        cookie_name = getattr(settings, "JWT_ACCESS_COOKIE_NAME", "jwt_token_in_cookie")
        # 写入 HttpOnly Cookie，生产环境启用 secure，降低 XSS 风险
        resp.set_cookie(
            cookie_name,
            access_token,
            httponly=True,
            secure=not settings.DEBUG,
            samesite="Lax",
            max_age=60 * 60 * 2,
        )


def _to_payload(data) -> dict:
    """
    将 request.data 转为普通 dict（兼容 QueryDict / OrderedDict）
    - 业务场景：视图层统一处理请求体，便于 Schema.from_dict
    - 参数 data: DRF Request.data 或 QueryDict
    """
    # 若对象支持 dict() 方法，优先调用确保保留多值键处理；否则直接强转
    if hasattr(data, "dict"):
        return data.dict()
    return dict(data)


class SendEmailVerificationView(APIView):
    """
    通用邮箱验证码发送接口
    - 适用场景：注册、找回密码、绑定邮箱
    - 仅负责参数校验与调用发送服务，限流交由 UserPostRateThrottle
    """

    # 公开接口，无需登录
    permission_classes = [AllowAny]
    # 限流：用户 POST 类场景
    throttle_classes = [EmailCodeSendRateThrottle, UserPostRateThrottle]

    @extend_schema(
        summary="发送邮箱验证码",
        tags=["accounts-email"],
        request=inline_serializer(
            name="SendEmailCodeRequest",
            fields={
                "email": serializers.EmailField(help_text="接收验证码的邮箱"),
                "scene": serializers.CharField(help_text="验证码场景，如 register/reset_password/bind_email/change_password"),
            },
        ),
        responses=api_response_schema(
            "SendEmailCode",
            {
                "sent": serializers.BooleanField(help_text="是否发送成功"),
                "expires_at": serializers.DateTimeField(help_text="验证码过期时间"),
                "debug_code": serializers.CharField(required=False, help_text="调试验证码，仅 DEBUG 返回"),
            },
        ),
    )
    def post(self, request: Request) -> Response:
        """
        发送验证码：
        - 从请求体构建 SendEmailCodeSchema（自动校验）
        - 执行发送服务；DEBUG 下输出 debug_code 便于测试
        """
        _ = self  # DRF 规格需实例方法，显式使用 self 抑制静态检查告警
        # 将请求数据转为 dict 并自动校验
        schema = SendEmailCodeSchema.from_dict(_to_payload(request.data), auto_validate=True)
        # 调用业务服务创建并发送验证码
        record = SendEmailVerificationService().execute(schema)
        # 安全日志：记录验证码发送行为
        log_security_event(
            action="send_email_code",
            request=request,
            username=None,
            user_id=getattr(request.user, "id", None),
            extra_fields={"email": schema.email, "scene": schema.scene},
        )
        # 构造响应载荷，包含失效时间；DEBUG 模式附带验证码
        payload: dict[str, object] = {"sent": True, "expires_at": record.expires_at.isoformat()}
        if settings.DEBUG:
            payload["debug_code"] = record.code
        # 统一成功响应格式
        return response.success(payload, message="验证码已发送")


class RegisterView(APIView):
    """用户注册接口：校验验证码与唯一性后创建账户"""

    # 公开接口，无需登录
    permission_classes = [AllowAny]
    # 限流：用户 POST 类场景
    throttle_classes = [RegisterRateThrottle, EmailCodeSendRateThrottle, UserPostRateThrottle]

    @extend_schema(
        tags=["accounts-auth"],
        summary="注册账户",
        request=inline_serializer(
            name="RegisterRequest",
            fields={
                "username": serializers.CharField(),
                "email": serializers.EmailField(),
                "password": serializers.CharField(),
                "confirm_password": serializers.CharField(),
                "email_code": serializers.CharField(),
                "nickname": serializers.CharField(required=False, allow_blank=True),
            },
        ),
        responses=api_response_schema("Register", {"user": user_summary_serializer()}),
    )
    def post(self, request: Request) -> Response:
        """
        提交注册：
        - 校验注册入参
        - 执行注册服务，创建用户并分配默认权限
        """
        _ = self
        # 构建并校验注册参数
        schema = RegisterSchema.from_dict(_to_payload(request.data), auto_validate=True)
        # 执行业务，创建用户
        user = RegisterService().execute(schema)
        # 返回 201 Created 响应，包含用户序列化信息
        return response.created({"user": serialize_user(user)}, message="注册成功")


class LoginView(APIView):
    """用户登录接口：返回 JWT（刷新/访问）"""

    # 公开接口，无需登录
    permission_classes = [AllowAny]
    # 登录限流：使用登录专用节流器
    throttle_classes = [LoginRateThrottle]

    @extend_schema(
        tags=["accounts-auth"],
        summary="登录账户",
        request=inline_serializer(
            name="LoginRequest",
            fields={
                "identifier": serializers.CharField(help_text="用户名或邮箱"),
                "password": serializers.CharField(),
                "captcha_key": serializers.CharField(required=False, allow_blank=True),
                "captcha_code": serializers.CharField(required=False, allow_blank=True),
            },
        ),
        responses=api_response_schema(
            "Login",
            {
                "access": serializers.CharField(help_text="访问令牌"),
                "refresh": serializers.CharField(help_text="刷新令牌"),
                "user": user_summary_serializer(),
            },
        ),
        examples=[
            OpenApiExample(
                "登录请求示例",
                value={
                    "identifier": "alice 或 alice@example.com",
                    "password": "Passw0rd123",
                    "captcha_key": "abcd1234",
                    "captcha_code": "XyZ1",
                },
                description="captcha_key/captcha_code 由获取验证码接口返回与输入",
            )
        ],
    )
    def post(self, request: Request) -> Response:
        """
        登录流程：
        - 校验 identifier/password
        - 校验 captcha_key/captcha_code 图形验证码
        - 执行 LoginService 获取 token 与用户信息
        - 写入 HttpOnly JWT Cookie（可配置关闭）
        """
        _ = self
        # 构建并校验登录参数
        schema = LoginSchema.from_dict(_to_payload(request.data), auto_validate=True)
        identifier_lower = schema.identifier.lower()
        # 登录失败次数锁定：按用户和 IP 双维度
        max_fail = 5
        block_seconds = 300
        ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or request.META.get("REMOTE_ADDR", "")
        user_key = redis_keys.login_fail_user_key(identifier_lower)
        ip_key = redis_keys.login_fail_ip_key(ip)

        def _check_block():
            for key in (user_key, ip_key):
                val = cache.get(key)
                if val is not None:
                    try:
                        if int(val) >= max_fail:
                            raise RateLimitError(message="登录失败次数过多，请稍后再试")
                    except ValueError:
                        cache.delete(key)

        _check_block()

        # 执行业务，获取 token 与用户信息
        try:
            data = LoginService().execute(schema)
        except BizError as exc:
            # 失败计数 + 安全日志
            for key in (user_key, ip_key):
                try:
                    val = cache.get(key) or 0
                    cache.set(key, int(val) + 1, timeout=block_seconds)
                except Exception:
                    pass
            # 登录失败安全日志
            log_security_event(
                action="login_failed",
                request=request,
                username=schema.identifier,
                user_id=None,
                detail=exc.message,
            )
            raise
        # 登录成功安全日志
        log_security_event(
            action="login_success",
            request=request,
            username=schema.identifier,
            user_id=data["user"].get("id") if isinstance(data.get("user"), dict) else None,
        )
        # 成功后清空失败计数
        cache.delete_many([user_key, ip_key])
        # 组装响应数据
        resp = response.success(
            {
                "access": data["access"],
                "refresh": data["refresh"],
                "user": data["user"],
            },
            message="登录成功",
        )
        # 根据配置写入 JWT Cookie
        _set_jwt_cookie(resp, access_token=str(data["access"]))
        return resp


class TokenRefreshView(APIView):
    """刷新访问令牌：使用 refresh 获取新的 access（可选返回 user）"""

    permission_classes = [AllowAny]

    @extend_schema(
        summary="刷新访问令牌",
        tags=["accounts-auth"],
        request=inline_serializer(
            name="TokenRefreshRequest",
            fields={
                "refresh": serializers.CharField(help_text="刷新令牌"),
            },
        ),
        responses=api_response_schema(
            "TokenRefresh",
            {
                "access": serializers.CharField(help_text="新的访问令牌"),
                "refresh": serializers.CharField(help_text="刷新令牌，可继续使用"),
                "user": user_summary_serializer(),
            },
        ),
    )
    def post(self, request: Request) -> Response:
        _ = self
        payload = _to_payload(request.data)
        refresh_token = payload.get("refresh")
        if not refresh_token:
            raise ValidationError(message="缺少 refresh 字段")
        try:
            token = RefreshToken(refresh_token)
            access = str(token.access_token)
            user_id = token.get("user_id")
        except Exception as exc:  # noqa: BLE001
            raise TokenError(message="刷新令牌无效或已过期，请重新登录") from exc

        user_data = None
        if user_id:
            from .models import User  # 局部导入避免循环

            user = User.objects.filter(pk=user_id).first()
            if user:
                user_data = serialize_user(user)

        resp = response.success(
            {
                "access": access,
                "refresh": str(token),
                "user": user_data,
            },
            message="刷新成功",
        )
        _set_jwt_cookie(resp, access_token=access)
        return resp


class CaptchaView(APIView):
    """
    获取登录图形验证码：
    - 返回 captcha_key 与验证码图片 URL
    - 前端需输入验证码并连同 key 传给登录接口
    """

    permission_classes = [AllowAny]
    # 禁用 JWT 认证，避免携带无效 Token 时返回 401
    authentication_classes = []

    @extend_schema(
        summary="获取图形验证码",
        tags=["accounts-auth"],
        request=None,
        responses=api_response_schema(
            "Captcha",
            {
                "captcha_key": serializers.CharField(),
                "image_url": serializers.CharField(),
            },
        ),
    )
    def get(self, request: Request) -> Response:
        _ = request
        # 生成验证码并返回图片地址与 key
        key = CaptchaStore.generate_key()
        image_url = captcha_image_url(key)
        return response.success({"captcha_key": key, "image_url": image_url}, message="验证码已生成")


class PasswordResetRequestView(APIView):
    """申请重置密码：发送重置场景的验证码"""

    # 公开接口
    permission_classes = [AllowAny]
    # 发送验证码走用户 POST 限流
    throttle_classes = [UserPostRateThrottle]

    @extend_schema(
        tags=["accounts-password"],
        request=inline_serializer(
            name="PasswordResetRequest",
            fields={
                "email": serializers.EmailField(),
            },
        ),
        responses=api_response_schema("PasswordResetSend", {"sent": serializers.BooleanField()}),
    )
    def post(self, request: Request) -> Response:
        """
        申请重置：
        - 将场景设置为 RESET_PASSWORD
        - 调用发送验证码服务
        """
        _ = self
        # 转换请求数据并指定场景
        payload = _to_payload(request.data)
        payload["scene"] = EmailVerificationCode.Scene.RESET_PASSWORD
        # 校验并执行发送
        schema = SendEmailCodeSchema.from_dict(payload, auto_validate=True)
        SendEmailVerificationService().execute(schema)
        return response.success(message="验证码已发送")


class PasswordResetView(APIView):
    """通过验证码重置密码"""

    # 公开接口
    permission_classes = [AllowAny]
    # 用户 POST 限流
    throttle_classes = [UserPostRateThrottle]

    @extend_schema(
        tags=["accounts-password"],
        request=inline_serializer(
            name="PasswordReset",
            fields={
                "email": serializers.EmailField(),
                "code": serializers.CharField(help_text="邮箱验证码"),
                "new_password": serializers.CharField(),
                "confirm_password": serializers.CharField(),
            },
        ),
        responses=api_response_schema("PasswordReset", {}),
    )
    def post(self, request: Request) -> Response:
        """
        重置密码：
        - 校验重置入参（邮箱/验证码/新密码）
        - 调用服务消费验证码并写入新密码
        """
        _ = self
        # 构建并校验重置参数
        schema = ResetPasswordSchema.from_dict(_to_payload(request.data), auto_validate=True)
        # 执行业务重置密码
        ResetPasswordService().execute(schema)
        return response.success(message="密码已重置，请重新登录")


class ProfileView(APIView):
    """用户个人资料接口：获取/更新当前登录用户信息"""

    # 需要登录
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="获取当前用户资料",
        tags=["accounts-profile"],
        request=None,
        responses=api_response_schema("ProfileDetail", {"user": user_summary_serializer()}),
    )
    def get(self, request: Request) -> Response:
        """获取当前用户资料"""
        _ = self
        return response.success({"user": serialize_user(request.user)})

    @extend_schema(
        summary="更新个人资料",
        tags=["accounts-profile"],
        request=inline_serializer(
            name="ProfileUpdate",
            fields={
                "nickname": serializers.CharField(required=False, allow_blank=True),
                "avatar": serializers.CharField(required=False, allow_blank=True),
                "bio": serializers.CharField(required=False, allow_blank=True),
                "organization": serializers.CharField(required=False, allow_blank=True),
                "country": serializers.CharField(required=False, allow_blank=True),
                "website": serializers.CharField(required=False, allow_blank=True),
            },
        ),
        responses=api_response_schema("ProfileUpdate", {"user": user_summary_serializer()}),
    )
    def patch(self, request: Request) -> Response:
        """
        部分更新个人资料：
        - 校验至少包含一个可更新字段
        - 调用更新服务后返回最新用户信息
        """
        _ = self
        # 构建并校验资料更新参数
        schema = ProfileUpdateSchema.from_dict(_to_payload(request.data), auto_validate=True)
        # 执行业务更新用户字段
        user = UpdateProfileService().execute(request.user, schema)
        return response.success({"user": serialize_user(user)}, message="资料已更新")


class AvatarUploadView(APIView):
    """
    头像上传接口：需登录，上传图片文件并更新当前用户头像
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    @extend_schema(
        summary="上传头像",
        tags=["accounts-profile"],
        request=inline_serializer(
            name="AvatarUpload",
            fields={
                "avatar": serializers.FileField(help_text="头像图片文件"),
            },
        ),
        responses=api_response_schema(
            "AvatarUpload",
            {
                "avatar": serializers.CharField(help_text="头像访问 URL"),
            },
        ),
    )
    def post(self, request: Request) -> Response:
        """
        上传并更新头像：
        - 校验图片类型与大小
        - 保存后返回头像 URL
        """
        _ = self
        uploaded_file = request.FILES.get("avatar")
        schema = AvatarUploadSchema.from_dict({"file": uploaded_file}, auto_validate=True)
        avatar_url = AvatarUploadService().execute(request.user, schema)
        return response.success({"avatar": avatar_url}, message="头像已更新")


class ChangePasswordView(APIView):
    """修改密码接口：需登录并提供旧密码与邮箱验证码"""

    # 需要登录
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["accounts-password"],
        request=inline_serializer(
            name="ChangePassword",
            fields={
                "old_password": serializers.CharField(),
                "email_code": serializers.CharField(),
                "new_password": serializers.CharField(),
                "confirm_password": serializers.CharField(),
            },
        ),
        responses=api_response_schema("ChangePassword", {}),
    )
    def post(self, request: Request) -> Response:
        """
        修改密码：
        - 校验旧密码、邮箱验证码、新密码与确认密码
        - 调用服务写入新密码
        """
        _ = self
        # 构建并校验修改密码参数
        schema = ChangePasswordSchema.from_dict(_to_payload(request.data), auto_validate=True)
        # 执行密码变更
        ChangePasswordService().execute(request.user, schema)
        return response.success(message="密码已更新")


class ChangeEmailView(APIView):
    """修改邮箱接口：需登录，验证当前密码与验证码"""

    # 需要登录
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["accounts-email"],
        request=inline_serializer(
            name="ChangeEmail",
            fields={
                "new_email": serializers.EmailField(),
                "email_code": serializers.CharField(),
                "current_password": serializers.CharField(),
            },
        ),
        responses=api_response_schema("ChangeEmail", {"user": user_summary_serializer()}),
    )
    def post(self, request: Request) -> Response:
        """
        修改邮箱：
        - 校验当前密码
        - 消费绑定邮箱验证码
        - 更新邮箱并返回最新资料
        """
        _ = self
        # 构建并校验修改邮箱参数
        schema = ChangeEmailSchema.from_dict(_to_payload(request.data), auto_validate=True)
        # 执行业务修改邮箱
        user = ChangeEmailService().execute(request.user, schema)
        return response.success({"user": serialize_user(user)}, message="邮箱已更新")


class DeleteAccountView(APIView):
    """注销账户接口：需登录并验证密码后软删除账户"""

    # 需要登录
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="注销账号",
        tags=["accounts-profile"],
        request=inline_serializer(
            name="DeleteAccount",
            fields={
                "password": serializers.CharField(),
            },
        ),
        responses=api_response_schema("DeleteAccount", {}),
    )
    def post(self, request: Request) -> Response:
        """
        注销流程：
        - 校验当前密码
        - 调用服务进行软删除处理（禁用账号、清除可识别信息）
        """
        _ = self
        # 构建并校验注销参数
        schema = DeleteAccountSchema.from_dict(_to_payload(request.data), auto_validate=True)
        # 执行业务注销账号
        DeleteAccountService().execute(request.user, schema)
        return response.success(message="账号已注销，当前会话即将失效")
