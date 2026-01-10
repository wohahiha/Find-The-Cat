"""
自定义全局异常处理器（DRF 入口）：
- 业务目的：统一前端收到的错误结构，区分业务错误与系统异常
- 处理策略：
  1) BizError 及子类 → 直接转换为 {code, message, data, extra}
  2) DRF 内置异常（Validation/Authentication/Permission/NotFound/Throttled）→ 映射为 BizError，再统一输出
  3) 未知/系统异常 → 记录完整日志，返回 500 标准格式，避免泄露内部信息
"""

from typing import Any

from rest_framework import status
from rest_framework.exceptions import (
    ValidationError as DRFValidationError,
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied as DRFPermissionDenied,
    NotFound as DRFNotFound,
    Throttled,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from .exceptions import (
    BizError,
    ValidationError as BizValidationError,
    AuthError,
    PermissionDeniedError,
    NotFoundError,
    RateLimitError,
)
from .response import api_response, payload_from_biz_error
from .infra.logger import get_logger
from .utils.request_context import get_request_context

logger = get_logger(__name__)


def _extract_message(detail: Any) -> str:
    """
    从 DRF 的 detail 结构中提取“第一条可读错误信息”

    detail 可能是：
    - str
    - list[detail]
    - dict[field -> detail]
    - 其他奇怪结构（就当 str(detail)）
    """
    if isinstance(detail, str):
        return detail

    if isinstance(detail, list) and detail:
        return _extract_message(detail[0])

    if isinstance(detail, dict) and detail:
        # 取第一个字段的第一个错误
        first_value = next(iter(detail.values()))
        return _extract_message(first_value)

    return str(detail)


def _handle_biz_error(exc: BizError) -> Response:
    """
    直接把 BizError 转成统一响应
    """
    payload = payload_from_biz_error(exc)
    return Response(payload, status=exc.http_status)


def _handle_unexpected_exception(exc: Exception, context: dict) -> Response:
    """
    处理不是 BizError、不是 DRF 异常的“程序 bug”：
    - 记录完整异常堆栈到日志；
    - 返回统一的 500 错误响应（不泄露内部细节）
    """
    ctx = get_request_context()
    req = context.get("request")
    user = getattr(req, "user", None)
    logger.exception(
        "Unhandled exception in API",
        exc_info=exc,
        extra={
            "path": getattr(req, "path", None),
            "method": getattr(req, "method", None),
            "user_id": getattr(user, "id", None) if user and getattr(user, "is_authenticated", False) else None,
        },
    )

    return api_response(
        code=50000,
        message="内部服务器错误，请联系管理员或稍后重试",
        data=None,
        http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        extra={
            "view": context.get("view").__class__.__name__ if context.get("view") else None,
            "request_path": getattr(context.get("request"), "path", None),
            "request_id": ctx.get("request_id"),
        },
    )


def _map_drf_exception_to_biz(exc: Exception) -> BizError | None:
    """
    尝试把 DRF 内置异常映射为我们的 BizError 子类
    映射不到就返回 None
    """
    # 参数校验错误（Serializer / 校验器抛的异常）
    if isinstance(exc, DRFValidationError):
        message = _extract_message(exc.detail)
        return BizValidationError(message=message, extra={"raw_detail": exc.detail})

    # 认证失败 / 未登录
    if isinstance(exc, (AuthenticationFailed, NotAuthenticated)):
        return AuthError(message=_extract_message(getattr(exc, "detail", str(exc))))

    # 权限不足
    if isinstance(exc, DRFPermissionDenied):
        return PermissionDeniedError(message=_extract_message(getattr(exc, "detail", str(exc))))

    # 资源不存在
    if isinstance(exc, DRFNotFound):
        return NotFoundError(message=_extract_message(getattr(exc, "detail", str(exc))))

    # 频率限制
    if isinstance(exc, Throttled):
        # exc.detail 通常是一个 dict / ErrorDetail
        message = _extract_message(getattr(exc, "detail", str(exc)))
        extra = {
            "wait": getattr(exc, "wait", None),
            "raw_detail": getattr(exc, "detail", None),
        }
        return RateLimitError(message=message, extra=extra)

    return None


def custom_exception_handler(exc: Exception, context: dict) -> Response | None:
    """
    DRF 入口函数：全局异常处理器

    处理顺序：
    1. 业务异常（BizError） → 直接按我们的格式返回；
    2. DRF 内置异常 → 尝试映射为 BizError 子类 → 按业务异常格式返回；
    3. 其它异常 →
        3.1 先交给 DRF 默认 handler，让它生成一个 Response；
        3.2 如果 DRF 能处理，则把它的结果“包一层”映射成统一结构；
        3.3 如果 DRF 也搞不定，视为真正的系统异常，返回 500
    """

    # 1) 我们自己的业务异常（BizError）
    if isinstance(exc, BizError):
        return _handle_biz_error(exc)

    # 2) 尝试把 DRF 内置异常映射为 BizError
    mapped = _map_drf_exception_to_biz(exc)
    if mapped is not None:
        return _handle_biz_error(mapped)

    # 3) 交给 DRF 默认异常处理器，看它能不能给出一个 Response
    drf_response = drf_exception_handler(exc, context)

    if drf_response is not None:
        # DRF 已经帮我们生成了 Response（一般是 ValidationError、404 等）
        # 为了保持统一格式，再包一层：
        raw_data = drf_response.data  # 原始数据
        message = _extract_message(raw_data)  # 提取消息
        status_code = drf_response.status_code  # HTTP 状态码

        # 状态码 < 500 → 一般视作请求 / 权限类异常
        if status_code < 500:
            code = 40000
        else:
            code = 50000

        return api_response(
            code=code,
            message=message,
            data=None,
            http_status=status_code,
            extra={"raw": raw_data},
        )

    # 4) DRF 也没处理（通常是 RuntimeError / 程序 bug）
    return _handle_unexpected_exception(exc, context)
