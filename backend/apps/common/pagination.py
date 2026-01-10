"""
自定义分页器（apps.common.pagination）

设计目标：
- 统一分页响应结构，与 common.response.page_success 对齐；
- 保留 DRF PageNumberPagination 默认参数行为（页码、page_size）；
- 控制默认分页大小/最大分页大小，防止一次拉取过多数据；
- 自动封装 {code,message,data,extra}，extra 内包含页码/总数/是否有前后页
"""

from __future__ import annotations

from typing import Any, List

from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.response import page_success


class StandardPagination(PageNumberPagination):
    """
    标准分页器（默认分页方案）

    参数说明：
    - page_size：默认每页大小（20）
    - page_size_query_param：允许前端通过 ?page_size=xxx 指定每页大小
    - max_page_size：前端可指定的最大单页数量（防止一次性拉过多）
    """

    page_size: int = 20
    page_size_query_param: str = "page_size"
    max_page_size: int = 100

    def get_paginated_response(self, data: List[Any]) -> Response:
        """
        将分页后的数据封装为统一格式

        注意：
        - self.page：当前页对象
        - self.page.paginator：分页器对象（包含总数 / 分页信息）
        """
        return page_success(
            items=data,  # 当前页数据列表
            page=self.page.number,  # 当前页码（从 1 开始）
            page_size=self.page.paginator.per_page,  # 后端实际使用的 page_size
            total=self.page.paginator.count,  # 数据总条数
            total_pages=self.page.paginator.num_pages,  # 总页数
            has_next=self.page.has_next(),  # 是否有下一页
            has_previous=self.page.has_previous(),  # 是否有上一页
            next_page=self.page.next_page_number() if self.page.has_next() else None,
            previous_page=self.page.previous_page_number() if self.page.has_previous() else None,
        )

    def get_page_size(self, request: Request) -> int | None:
        """
        覆写以增加最小值校验，防止 page_size 为 0 或负值
        """
        size = super().get_page_size(request)
        if size is None:
            return None
        return max(1, size)
