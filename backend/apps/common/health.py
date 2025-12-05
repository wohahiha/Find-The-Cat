from __future__ import annotations

from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common import response
from apps.common.permissions import AllowAny


class HealthCheckView(APIView):
    """
    健康检查接口
    - 用于负载均衡/监控探活，返回统一成功格式
    - 不做昂贵检查，保持快速响应
    """

    permission_classes = [AllowAny]

    @staticmethod
    def get(request: Request) -> Response:
        """返回简单 OK 状态"""
        _ = request
        return response.success({"status": "ok"})
