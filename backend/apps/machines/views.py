from __future__ import annotations

from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiParameter
from rest_framework import serializers

from apps.common import response
from apps.common.permissions import IsAuthenticated, BizPermission
from apps.common.throttles import MachineStartRateThrottle
from apps.common.pagination import StandardPagination
from apps.common.schema_utils import api_response_schema, list_response, machine_serializer, pagination_parameters

from .schemas import MachineStartSchema, MachineStopSchema, MachineExtendSchema
from .services import MachineStartService, MachineStopService, MachineExtendService, serialize_machine
from .repo import MachineRepo


# 视图层：提供靶机启动、停止与列表接口


class MachineListCreateView(APIView):
    """
    靶机列表/启动接口：
    - GET：查询当前用户的靶机实例
    - POST：为指定比赛/题目启动靶机
    """

    permission_classes = [IsAuthenticated, BizPermission]
    biz_permission_map = {
        "get": "machines.view_machine",
        "post": "machines.start_machine",
    }
    throttle_classes = [MachineStartRateThrottle]
    pagination_class = StandardPagination
    repo = MachineRepo()
    start_service = MachineStartService()

    @extend_schema(
        summary="我的靶机列表",
        request=None,
        responses=list_response("MachineList", machine_serializer(), paginated=True),
        parameters=pagination_parameters(),
    )
    def get(self, request: Request) -> Response:
        # 查询当前登录用户“运行中”的实例，按创建时间倒序；已停止实例不再返回
        queryset = (
            self.repo.filter(user=request.user, status=self.repo.model.Status.RUNNING)
            .select_related("contest", "challenge", "team")
            .order_by("-created_at")
        )
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        data = [serialize_machine(m) for m in page]
        return paginator.get_paginated_response({"items": data})

    @extend_schema(
        summary="启动靶机",
        request=inline_serializer(
            name="MachineStartRequest",
            fields={
                "contest_slug": serializers.CharField(help_text="比赛标识"),
                "challenge_slug": serializers.CharField(help_text="题目标识"),
            },
        ),
        responses=api_response_schema("MachineStart", {"machine": machine_serializer()}),
    )
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

    permission_classes = [IsAuthenticated, BizPermission]
    biz_permission = "machines.stop_machine"
    stop_service = MachineStopService()

    @extend_schema(
        summary="停止靶机",
        request=None,
        responses=api_response_schema("MachineStop", {"machine": machine_serializer()}),
    )
    def post(self, request: Request, machine_id: int) -> Response:
        # 路径参数 machine_id 指定要停止的实例
        schema = MachineStopSchema.from_dict({"machine_id": machine_id}, auto_validate=True)
        instance = self.stop_service.execute(request.user, schema)
        return response.success({"machine": serialize_machine(instance)}, message="靶机已停止")


class MachineExtendView(APIView):
    """
    延长靶机运行时间：
    - 仅运行中的实例可延长
    """

    permission_classes = [IsAuthenticated, BizPermission]
    # 使用 stop_machine 权限即可（与停止行为同级）
    biz_permission = "machines.stop_machine"
    extend_service = MachineExtendService()

    @extend_schema(
        summary="延长靶机运行时间",
        request=inline_serializer(
            name="MachineExtendRequest",
            fields={
                "minutes": serializers.IntegerField(required=False, allow_null=True, help_text="可选：本次延长的分钟数，不填使用默认值"),
            },
        ),
        responses=api_response_schema("MachineExtend", {"machine": machine_serializer()}),
    )
    def post(self, request: Request, machine_id: int) -> Response:
        schema = MachineExtendSchema.from_dict(
            {
                "machine_id": machine_id,
                "minutes": request.data.get("minutes"),
            },
            auto_validate=True,
        )
        instance = self.extend_service.execute(request.user, schema)
        return response.success({"machine": serialize_machine(instance)}, message="靶机已延长")
