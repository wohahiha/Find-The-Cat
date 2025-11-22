from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common import response

# 视图骨架：后续提供靶机启动/停止接口。


class MachinePlaceholderView(APIView):
    """
    占位接口：
    - 仅返回提示信息，提醒后续补充靶机管理逻辑。
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        return response.success(message="Machines 模块尚未实现，敬请期待")
