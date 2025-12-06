from __future__ import annotations

from django.conf import settings
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers

from apps.common.permissions import AllowAny
from apps.common import response
from .services import ConfigService


class PublicBrandView(APIView):
    """
    对外公开的品牌配置接口

    场景：
    - 前端在启动时读取品牌名，替换导航、页眉、页脚的“Find The Cat”
    - 品牌可由管理员在后台 SystemConfig 中修改（键：SITE_BRAND）
    """

    permission_classes = [AllowAny]

    @extend_schema(
        summary="获取站点品牌名",
        description="平台前台展示的站点品牌名，默认为 'Find The Cat'",
        responses=inline_serializer(
            name="PublicBrandResponse",
            fields={
                "code": serializers.IntegerField(),
                "message": serializers.CharField(),
                "data": inline_serializer(
                    name="PublicBrandData",
                    fields={
                        "brand": serializers.CharField(help_text="站点品牌名称，来自 SystemConfig 或 settings.SITE_BRAND"),
                    },
                ),
            },
        ),
    )
    def get(self, request, *args, **kwargs):
        config = ConfigService()
        default_brand = getattr(settings, "SITE_BRAND", "Find The Cat")
        brand = config.get("SITE_BRAND", default_brand)
        return response.api_response(data={"brand": brand})
