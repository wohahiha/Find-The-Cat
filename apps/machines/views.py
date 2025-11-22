from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common import response

from .schemas import MachineStartSchema, MachineStopSchema
from .services import MachineStartService, MachineStopService, serialize_machine
from .repo import MachineRepo

# 视图层：提供靶机启动、停止与列表接口。


class MachineListCreateView(APIView):
    """
    靶机列表/启动接口：
    - GET：查询当前用户的靶机实例。
    - POST：为指定比赛/题目启动靶机。
    """

    permission_classes = [IsAuthenticated]
    repo = MachineRepo()
    start_service = MachineStartService()

    def get(self, request: Request) -> Response:
        queryset = self.repo.filter(user=request.user).order_by("-created_at")
        data = [serialize_machine(m) for m in queryset]
        return response.success({"items": data})

    def post(self, request: Request) -> Response:
        schema = MachineStartSchema.from_dict(request.data, auto_validate=True)
        instance = self.start_service.execute(request.user, schema)
        return response.created({"machine": serialize_machine(instance)}, message="靶机已启动")


class MachineStopView(APIView):
    """
    靶机停止接口：
    - POST：停止指定实例。
    """

    permission_classes = [IsAuthenticated]
    stop_service = MachineStopService()

    def post(self, request: Request, machine_id: int) -> Response:
        schema = MachineStopSchema.from_dict({"machine_id": machine_id}, auto_validate=True)
        instance = self.stop_service.execute(request.user, schema)
        return response.success({"machine": serialize_machine(instance)}, message="靶机已停止")
