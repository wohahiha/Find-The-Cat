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
from drf_spectacular.utils import extend_schema
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample
from captcha.models import CaptchaStore
from captcha.helpers import captcha_image_url

from apps.common import response
from apps.common.permissions import IsAuthenticated, AllowAny
from apps.common.throttles import LoginRateThrottle, UserPostRateThrottle

from .models import EmailVerificationCode
from .schemas import (
    SendEmailCodeSchema,
    RegisterSchema,
    LoginSchema,
    ResetPasswordSchema,
    ProfileUpdateSchema,
    ChangePasswordSchema,
    ChangeEmailSchema,
    DeleteAccountSchema,
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
)


def _set_jwt_cookie(resp: Response, access_token: str) -> None:
    """
    根据配置决定是否写入 JWT Cookie
    - 业务场景：登录成功后可选择把 access token 写入 HttpOnly Cookie，便于前端少操作
    - 参数 resp: DRF Response 对象；access_token: JWT 访问令牌
    """
    # 默认开启 Cookie 模式，可通过设置关闭
    if getattr(settings, "JWT_USE_COOKIE", True):
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
    throttle_classes = [UserPostRateThrottle]

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
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
    throttle_classes = [UserPostRateThrottle]

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
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
        request=OpenApiTypes.OBJECT,
        responses=OpenApiTypes.OBJECT,
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
        # 执行业务，获取 token 与用户信息
        data = LoginService().execute(schema)
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


class CaptchaView(APIView):
    """
    获取登录图形验证码：
    - 返回 captcha_key 与验证码图片 URL
    - 前端需输入验证码并连同 key 传给登录接口
    """

    permission_classes = [AllowAny]

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    def get(self, request: Request) -> Response:
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

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
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

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
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

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    def get(self, request: Request) -> Response:
        """获取当前用户资料"""
        _ = self
        return response.success({"user": serialize_user(request.user)})

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
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


class ChangePasswordView(APIView):
    """修改密码接口：需登录并提供旧密码"""

    # 需要登录
    permission_classes = [IsAuthenticated]

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request) -> Response:
        """
        修改密码：
        - 校验旧密码、新密码与确认密码
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

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
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

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
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
