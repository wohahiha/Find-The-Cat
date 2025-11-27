from __future__ import annotations

from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from drf_spectacular.types import OpenApiTypes

from apps.common import response
from apps.common.permissions import IsAuthenticated
from apps.common.throttles import MachineStartRateThrottle
from apps.common.pagination import StandardPagination

from .schemas import MachineStartSchema, MachineStopSchema
from .services import MachineStartService, MachineStopService, serialize_machine
from .repo import MachineRepo


# 视图层：提供靶机启动、停止与列表接口


class MachineListCreateView(APIView):
    """
    靶机列表/启动接口：
    - GET：查询当前用户的靶机实例
    - POST：为指定比赛/题目启动靶机
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [MachineStartRateThrottle]
    repo = MachineRepo()
    start_service = MachineStartService()

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    def get(self, request: Request) -> Response:
        # 查询当前登录用户的所有实例，按创建时间倒序
        queryset = (
            self.repo.filter(user=request.user)
            .select_related("contest", "challenge", "team")
            .order_by("-created_at")
        )
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        data = [serialize_machine(m) for m in page]
        return paginator.get_paginated_response({"items": data})

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request) -> Response:
        # 通过 Schema 校验后调用服务启动新靶机
        schema = MachineStartSchema.from_dict(request.data, auto_validate=True)
        instance = self.start_service.execute(request.user, schema)
        return response.created({"machine": serialize_machine(instance)}, message="靶机已启动")


class MachineStopView(APIView):
    """
    靶机停止接口：
    - POST：停止指定实例
    """

    permission_classes = [IsAuthenticated]
    stop_service = MachineStopService()

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request, machine_id: int) -> Response:
        # 路径参数 machine_id 指定要停止的实例
        schema = MachineStopSchema.from_dict({"machine_id": machine_id}, auto_validate=True)
        instance = self.stop_service.execute(request.user, schema)
        return response.success({"machine": serialize_machine(instance)}, message="靶机已停止")
