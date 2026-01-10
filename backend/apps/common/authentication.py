"""
统一 JWT 认证封装（apps.common.authentication）

职责与目标：
- 全局 JWT 认证入口，统一 Header/Cookie 取 Token 的逻辑
- 将 JWT 相关异常映射到 BizError（TokenError/AuthError），交由全局异常处理器统一格式化响应
- 后续若需调整“Token 传递方式/前缀/Cookie 名称”集中改此处

默认行为（兼容 SimpleJWT）：
- 优先从 Authorization 头读取：Authorization: Bearer <token>
- 可选从 Cookie 读取：jwt_token_in_cookie=<token>（可通过类属性调整）
- 未提供凭证 → 返回 None（匿名，由权限类决定是否放行）
- 凭证无效/过期 → TokenError(40102)；其他认证失败 → AuthError(40100)
"""

from __future__ import annotations

from typing import Any, Optional

from django.conf import settings
from rest_framework.request import Request
from rest_framework_simplejwt.authentication import (
    JWTAuthentication as SimpleJWTAuthentication,
)
from rest_framework_simplejwt.exceptions import (
    InvalidToken,
    AuthenticationFailed as SimpleJWTAuthFailed,
)

from .exceptions import TokenError, AuthError
from .infra.logger import get_logger, logger_extra
from .utils.request_context import update_request_user

logger = get_logger(__name__)


class JWTAuthentication(SimpleJWTAuthentication):
    """
    统一 JWT 认证入口

    可配置点：
    - use_cookie: 是否允许从 cookie 读取 access token；
    - cookie_name: cookie 中 jwt access token 的键名；
    - header_types: 继承自 SimpleJWT，可通过 SIMPLE_JWT['AUTH_HEADER_TYPES'] 或
      直接修改本类属性来调整（例如支持 Bearer / JWT 等前缀）
    """

    #: 是否允许从 Cookie 读取 access token
    # use_cookie 默认启用
    use_cookie: bool = getattr(settings, "JWT_USE_COOKIE", True)

    #: Cookie 中存放 access token 的键名
    # cookie_name 默认值为 "jwt_token_in_cookie"
    cookie_name: str = getattr(settings, "JWT_ACCESS_COOKIE_NAME", "jwt_token_in_cookie")

    def authenticate(self, request: Request) -> Optional[tuple[Any, Any]]:
        """
        统一认证入口

        返回：
            - (user, validated_token)：认证成功；
            - None：未提供任何凭证（交给后续权限系统处理）

        异常约定：
            - Token 无效 / 过期 / 被篡改：抛 TokenError(40102)；
            - 其他认证失败（例如用户被禁用等）：抛 AuthError(40100)

        注意：
        - 不再抛 DRF 的 AuthenticationFailed / InvalidToken 等异常，
          而是直接抛 BizError 子类，方便 custom_exception_handler 统一格式化
        """
        # 1. 尝试从 Authorization header 中获取 token
        header = self.get_header(request)
        raw_token: Optional[str] = None

        if header is not None:
            # SimpleJWT 的 get_raw_token 负责解析前缀（Bearer / JWT 等）
            raw_token = self.get_raw_token(header)

        # 2. 如果 header 中没有，再尝试从 cookie 中获取
        if raw_token is None and self.use_cookie:
            cookie_token = request.COOKIES.get(self.cookie_name)
            if cookie_token:
                raw_token = cookie_token

        # 3. 既没有 header 也没有 cookie → 视为“未提供凭证”，返回 None
        #    DRF 会认为当前请求是匿名用户，再由权限类决定是否允许访问
        if raw_token is None:
            return None

        # 4. 有 token，则执行验证流程
        try:
            validated_token = self.get_validated_token(raw_token)
            user = self.get_user(validated_token)
        except InvalidToken as exc:
            # Token 语法错误 / 过期 / 签名错误 / 被吊销等，统一为 TokenError
            # 具体错误原因不泄露给前端，只给出“登录状态失效”的友好提示
            logger.warning(
                "认证失败：无效或过期的 JWT",
                extra=logger_extra({"reason": "invalid_token"}),
            )
            raise TokenError(message="令牌无效或已过期，请重新登录") from exc
        except SimpleJWTAuthFailed as exc:
            # 其他认证失败情况（例如用户不存在、被禁用等）
            detail = getattr(exc, "detail", None)
            # detail 可能是 str / dict / ErrorDetail，统一转为 str
            message = str(detail) if detail is not None else "认证失败，请重新登录"
            logger.warning(
                "认证失败：用户校验失败",
                extra=logger_extra({"reason": message}),
            )
            raise AuthError(message=message) from exc

        # 5. 认证成功后更新请求上下文中的用户信息，确保后续日志拥有账户标识
        update_request_user(user)

        # 6. 返回 (user, validated_token)，与 SimpleJWT 接口保持一致
        return user, validated_token
