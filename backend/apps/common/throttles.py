"""
统一限速封装（apps.common.throttles）

职责：
- 覆盖 DRF 默认限速行为，统一抛 BizError（RateLimitError），保证响应格式
- 为登录、Flag 提交、启动靶机、通用 POST 等关键场景提供独立 throttle 类
- 支持基于 IP/用户的限速；保留 wait 秒数，便于前端展示倒计时
"""

from __future__ import annotations

from typing import Optional

from rest_framework.throttling import SimpleRateThrottle
from rest_framework.exceptions import Throttled

from .exceptions import RateLimitError
from apps.common.infra.logger import get_logger, logger_extra

logger = get_logger(__name__)


# ======================
# 小工具：统一把 DRF 的 Throttled → RateLimitError
# ======================

def raise_rate_limit(exc: Throttled) -> None:
    """
    将 DRF 内置 Throttled 映射为 RateLimitError，
    保留 wait 秒数字段，交给全局异常处理器统一格式化
    - 业务场景：任何触发 DRF Throttled 的地方都可复用，统一提示
    """
    wait = getattr(exc, "wait", None)
    detail = getattr(exc, "detail", None)
    message = str(detail) if detail else "请求过于频繁，请稍后再试"

    logger.warning(
        "限流触发",
        extra=logger_extra(
            {
                "detail": message,
            }
        ),
    )
    raise RateLimitError(
        message=message,
        extra={"wait": wait, "raw_detail": detail}
    ) from exc


# ======================
# 登录限速（按 IP）
# ======================

class LoginRateThrottle(SimpleRateThrottle):
    """
    登录接口限速（防止爆破）

    默认 scope = login
    key = throttle_login_<ip>
    """

    scope = "login"  # 对应 settings 中的 DEFAULT_THROTTLE_RATES 配置

    def get_cache_key(self, request, view) -> Optional[str]:
        ip = self.get_ident(request)
        return f"throttle_login_{ip}"

    def throttle_failure(self):
        """
        DRF 默认抛 Throttled，我们覆盖 → RateLimitError
        """
        exc = Throttled(detail="登录请求过于频繁，请稍后再试")
        raise_rate_limit(exc)


class RegisterRateThrottle(SimpleRateThrottle):
    """
    注册接口限速（防撞库）

    默认 scope = register
    key = throttle_register_<ip>
    """

    scope = "register"

    def get_cache_key(self, request, view) -> Optional[str]:
        ip = self.get_ident(request)
        return f"throttle_register_{ip}"

    def throttle_failure(self):
        exc = Throttled(detail="注册请求过于频繁，请稍后再试")
        raise_rate_limit(exc)


# ======================
# Flag 提交限速
# ======================

class FlagSubmitRateThrottle(SimpleRateThrottle):
    """
    Flag 提交接口限速（防暴力猜解）

    规则：
    - 登录用户 → 按 user_id 限速
    - 未登录用户（理论上不会访问）→ 按 IP 限速
    """

    scope = "flag_submit"  # 对应 settings 中的 DEFAULT_THROTTLE_RATES 配置

    def get_cache_key(self, request, view) -> Optional[str]:
        user = request.user

        # 已登录用户，按用户限速
        if user and user.is_authenticated:
            return f"throttle_flag_user_{user.pk}"

        # 理论不能到这里
        # 按 IP 限速
        ip = self.get_ident(request)
        return f"throttle_flag_ip_{ip}"

    def throttle_failure(self):
        exc = Throttled(detail="Flag 提交过于频繁，请稍后再提交")
        raise_rate_limit(exc)


# ======================
# 启动靶机限速
# ======================

class MachineStartRateThrottle(SimpleRateThrottle):
    """
    限制启动靶机的频率，防止资源滥用

    scope = machine_start
    key = throttle_machine_start_user_<uid>
    """

    scope = "machine_start"  # 对应 settings 中的 DEFAULT_THROTTLE_RATES 配置

    def get_cache_key(self, request, view) -> Optional[str]:
        user = request.user

        # 已登录用户，按用户限速
        if user and user.is_authenticated:
            return f"throttle_machine_start_user_{user.pk}"

        # 理论不能到这里
        # 按 IP 限速
        ip = self.get_ident(request)
        return f"throttle_machine_start_ip_{ip}"

    def throttle_failure(self):
        exc = Throttled(detail="启动靶机过于频繁，请稍后再试")
        raise_rate_limit(exc)


# ======================
# 通用 POST 限速
# ======================

class UserPostRateThrottle(SimpleRateThrottle):
    """
    全局 POST 限速：防脚本滥用通用接口

    scope = user_post
    """

    scope = "user_post"  # 对应 settings 中的 DEFAULT_THROTTLE_RATES 配置

    def get_cache_key(self, request, view) -> Optional[str]:
        # 仅限 POST 请求
        if request.method != "POST":
            return None

        user = request.user

        # 已登录用户，按用户限速
        if user and user.is_authenticated:
            return f"throttle_user_post_{user.pk}"

        # 理论不能到这里
        # 按 IP 限速
        ip = self.get_ident(request)
        return f"throttle_user_post_ip_{ip}"

    def throttle_failure(self):
        exc = Throttled(detail="操作过于频繁，请稍后再试")
        raise_rate_limit(exc)


# ======================
# 附件上传限速
# ======================

class AttachmentUploadRateThrottle(SimpleRateThrottle):
    """
    附件上传限速：
    - 防止大规模上传耗尽带宽与存储
    """

    scope = "attachment_upload"

    def get_cache_key(self, request, view) -> Optional[str]:
        # 仅限 POST 上传
        if request.method != "POST":
            return None
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            return f"throttle_attach_user_{user.pk}"
        ip = self.get_ident(request)
        return f"throttle_attach_ip_{ip}"

    def throttle_failure(self):
        exc = Throttled(detail="上传过于频繁，请稍后再试")
        raise_rate_limit(exc)


# ======================
# 邮箱验证码发送限速
# ======================

class EmailCodeSendRateThrottle(SimpleRateThrottle):
    """
    邮箱验证码发送限速：
    - 按邮箱优先，其次按 IP 限制发送频率，防止批量撞库
    """

    scope = "email_code_send"

    def get_cache_key(self, request, view) -> Optional[str]:
        if request.method != "POST":
            return None
        email = None
        try:
            data = getattr(request, "data", {}) or {}
            email = data.get("email")
        except Exception:
            email = None
        if email:
            return f"throttle_email_code_{email}"
        ip = self.get_ident(request)
        return f"throttle_email_code_ip_{ip}"

    def throttle_failure(self):
        exc = Throttled(detail="验证码发送过于频繁，请稍后再试")
        raise_rate_limit(exc)
