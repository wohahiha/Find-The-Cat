from __future__ import annotations

from django.utils.deprecation import MiddlewareMixin

from apps.common.utils.request_context import (
    clear_request_context,
    generate_request_id,
    set_request_context,
)


class RequestContextMiddleware(MiddlewareMixin):
    """
    在请求生命周期内写入 request_id、用户、方法、路径、IP，供日志过滤器使用
    """

    def process_request(self, request):
        user = getattr(request, "user", None)
        remote_ip = self._get_client_ip(request)
        set_request_context(
            request_id=request.headers.get("X-Request-ID") or generate_request_id(),
            user_id=getattr(user, "id", None) if user and user.is_authenticated else None,
            account_id=getattr(user, "account_id", None) if user and user.is_authenticated else None,
            username=getattr(user, "username", "") if user and user.is_authenticated else "",
            path=getattr(request, "path", ""),
            method=getattr(request, "method", ""),
            ip=remote_ip or "",
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )

    @staticmethod
    def process_response(request, response):
        _ = request
        clear_request_context()
        return response

    @staticmethod
    def process_exception(request, exception):
        _ = request
        _ = exception
        clear_request_context()
        return None

    @staticmethod
    def _get_client_ip(request):
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            return xff.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "")
