from __future__ import annotations

from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, inline_serializer
from rest_framework import serializers

from apps.common.permissions import IsAuthenticated, BizPermission
from apps.common.pagination import StandardPagination
from apps.common.response import success
from apps.common.schema_utils import api_response_schema, list_response, pagination_parameters

from .repo import NotificationRepo
from .services import (
    serialize_notification,
    NotificationMarkReadService,
    NotificationMarkAllReadService,
)


class NotificationListView(APIView):
    """通知列表：默认全部，可按未读过滤"""

    permission_classes = [IsAuthenticated, BizPermission]
    biz_permission = "notifications.view_notification"
    pagination_class = StandardPagination
    repo = NotificationRepo()
    mark_read_service = NotificationMarkReadService()

    @extend_schema(
        summary="通知列表",
        operation_id="notification_list",
        responses=list_response(
            "NotificationList",
            inline_serializer(
                name="NotificationItem",
                fields={
                    "id": serializers.IntegerField(),
                    "type": serializers.CharField(),
                    "title": serializers.CharField(),
                    "body": serializers.CharField(allow_blank=True),
                    "payload": serializers.DictField(required=False),
                    "contest": serializers.CharField(required=False, allow_null=True),
                    "team_id": serializers.IntegerField(required=False, allow_null=True),
                    "team_slug": serializers.CharField(required=False, allow_null=True),
                    "challenge": serializers.CharField(required=False, allow_null=True),
                    "read_at": serializers.DateTimeField(required=False, allow_null=True),
                    "expires_at": serializers.DateTimeField(required=False, allow_null=True),
                    "created_at": serializers.DateTimeField(),
                },
            ),
            paginated=True,
        ),
        parameters=[
            OpenApiParameter(
                name="status",
                location=OpenApiParameter.QUERY,
                required=False,
                description="筛选状态：unread/all（默认 all）",
                type=str,
                enum=["unread", "all"],
            ),
            *pagination_parameters(),
        ],
        tags=["notifications"],
    )
    def get(self, request: Request) -> Response:
        status_filter = request.query_params.get("status", "all")
        queryset = self.repo.filter(user=request.user).order_by("-created_at")
        if status_filter == "unread":
            queryset = queryset.filter(read_at__isnull=True)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        items = [serialize_notification(n) for n in page]
        return paginator.get_paginated_response(items)


class NotificationUnreadCountView(APIView):
    """未读计数"""

    permission_classes = [IsAuthenticated, BizPermission]
    biz_permission = "notifications.view_notification"
    repo = NotificationRepo()

    @extend_schema(
        summary="未读通知数量",
        operation_id="notification_unread_count",
        responses=api_response_schema(
            "NotificationUnreadCount",
            {
                "unread": serializers.IntegerField(help_text="未读数量"),
            },
        ),
        tags=["notifications"],
    )
    def get(self, request: Request) -> Response:
        count = self.repo.unread_count(request.user)
        return success({"unread": count})


class NotificationMarkReadView(APIView):
    """标记单条通知已读"""

    permission_classes = [IsAuthenticated, BizPermission]
    biz_permission = "notifications.view_notification"
    service = NotificationMarkReadService()

    @extend_schema(
        summary="标记通知已读",
        operation_id="notification_mark_read",
        request=None,
        responses=api_response_schema(
            "NotificationMarkRead",
            {"notification": inline_serializer(name="NotificationMarked", fields={"id": serializers.IntegerField()})},
        ),
        tags=["notifications"],
    )
    def post(self, request: Request, notification_id: int) -> Response:
        notif = self.service.execute(request.user, notification_id)
        return success({"notification": {"id": notif.id}})


class NotificationMarkAllReadView(APIView):
    """标记全部通知为已读"""

    permission_classes = [IsAuthenticated, BizPermission]
    biz_permission = "notifications.view_notification"
    service = NotificationMarkAllReadService()

    @extend_schema(
        summary="全部标记为已读",
        operation_id="notification_mark_all_read",
        request=None,
        responses=api_response_schema(
            "NotificationMarkAllRead",
            {"updated": serializers.IntegerField(help_text="被标记的通知数量")},
        ),
        tags=["notifications"],
    )
    def post(self, request: Request) -> Response:
        updated = self.service.execute(request.user)
        return success({"updated": updated}, message="已标记为已读")
