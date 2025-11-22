"""
统一 API 响应封装（common.response）

目标：
- 所有接口的返回结构保持一致，便于前端 & 调试；
- 业务代码里尽量只关心“code / message / data”，不直接接触 DRF Response；
- 和 BizError 体系对齐，方便异常处理器和正常返回使用同一套字段。

约定返回结构：
{
    "code": 0,            # 0 表示成功；非 0 表示业务错误
    "message": "OK",      # 提示信息（给人看的）
    "data": {...},        # 业务数据（任意结构；列表、字典、None 均可）
    "extra": {...}        # 可选，附加元信息（分页信息等），前后端约定使用
}
"""

from typing import Any, Mapping, Optional

from rest_framework import status
from rest_framework.response import Response

from .exceptions import BizError

# ======================
# 常量 & 类型
# ======================

SUCCESS_CODE = 0  # 约定：成功永远是 0

Payload = dict[str, Any]


# ======================
# Payload 构造器
# ======================

def build_payload(
        *,
        code: int = SUCCESS_CODE,
        message: str = "OK",
        data: Any = None,
        extra: Optional[Mapping[str, Any]] = None,
) -> Payload:
    """
    构造统一的响应字典，不涉及 HTTP/DRF。
    """
    payload: Payload = {
        "code": code,
        "message": message,
        "data": data,
    }
    if extra:
        payload["extra"] = dict(extra)
    return payload


def payload_from_biz_error(exc: BizError, data: Any = None) -> Payload:
    """
    根据 BizError 构造 payload。
    """
    return build_payload(
        code=exc.code,
        message=exc.message,
        data=data,
        extra=exc.extra,
    )


# ======================
# 分页元信息构造器
# ======================

def build_page_extra(
        *,
        page: int,
        page_size: int,
        total: int,
        has_next: bool,
        has_previous: bool,
) -> Mapping[str, Any]:
    """
    简单的分页元信息构造器。

    后续根据需要调整。
    """
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "has_next": has_next,
        "has_previous": has_previous,
    }


# ======================
# 对 DRF Response 的薄封装
# ======================

def api_response(
        *,
        code: int = SUCCESS_CODE,
        message: str = "OK",
        data: Any = None,
        http_status: int = status.HTTP_200_OK,
        extra: Optional[Mapping[str, Any]] = None,
) -> Response:
    """
    统一构造 DRF Response。
    """
    payload = build_payload(code=code, message=message, data=data, extra=extra)
    return Response(payload, status=http_status)


def success(data: Any = None, message: str = "OK") -> Response:
    """
    最常用：业务成功返回。

    - HTTP 状态：200
    - code：0
    """
    return api_response(
        code=SUCCESS_CODE,
        message=message,
        data=data,
        http_status=status.HTTP_200_OK,
    )


def created(data: Any = None, message: str = "Created") -> Response:
    """
    新建资源成功。

    - HTTP 状态：201
    - code：0
    """
    return api_response(
        code=SUCCESS_CODE,
        message=message,
        data=data,
        http_status=status.HTTP_201_CREATED,
    )


def no_content(message: str = "No Content") -> Response:
    """
    无内容返回（例如删除成功），仅保留 code/message。

    - HTTP 状态：204
    - data 固定为 None
    """
    return api_response(
        code=SUCCESS_CODE,
        message=message,
        data=None,
        http_status=status.HTTP_204_NO_CONTENT,
    )


def fail(
        *,
        code: int,
        message: str,
        http_status: int = status.HTTP_400_BAD_REQUEST,
        data: Any = None,
        extra: Optional[Mapping[str, Any]] = None,
) -> Response:
    """
    通用失败返回（手动构造，不走 BizError）。
    """
    return api_response(
        code=code,
        message=message,
        data=data,
        http_status=http_status,
        extra=extra,
    )


def response_from_biz_error(exc: BizError, data: Any = None) -> Response:
    """
    根据 BizError 构造 Response。
    """
    return api_response(
        code=exc.code,
        message=exc.message,
        data=data,
        http_status=exc.http_status,
        extra=exc.extra,
    )


def page_success(
        *,
        message: str = "OK",
        items: Any,  # 实际为 List[Any]

        page: int,
        page_size: int,
        total: int,
        has_next: bool,
        has_previous: bool,

) -> Response:
    """
    分页成功返回。

    结构示例：
    {
        "code": 0,
        "message": "OK",
        "data": [...],           # 当前页数据列表
        "extra": {
            "page": 1,
            "page_size": 20,
            "total": 120,
            "has_next": true,
            "has_previous": false
        }
    }
    """
    extra = build_page_extra(
        page=page,
        page_size=page_size,
        total=total,
        has_next=has_next,
        has_previous=has_previous,
    )
    return api_response(
        code=SUCCESS_CODE,
        message=message,
        data=items,
        http_status=status.HTTP_200_OK,
        extra=extra,
    )
