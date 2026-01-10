from __future__ import annotations

from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
import base64
from rest_framework import serializers
from django.db import models

from apps.common import response
from apps.common.response import page_success
from apps.common.exceptions import ValidationError
from apps.common.utils.validators import validate_upload_file
from apps.common.permissions import (
    IsAuthenticated,
    IsAdmin,
    IsAdminOrReadOnly,
    BizPermission,
)
from apps.common.pagination import StandardPagination
from apps.common.schema_utils import (
    api_response_schema,
    list_response,
    problem_bank_serializer,
    bank_challenge_serializer,
    pagination_parameters,
)

from .serializers import serialize_bank, serialize_challenge
from .services import (
    ProblemBankCreateService,
    ProblemBankUpdateService,
    BankImportFromContestService,
    BankImportChallengesService,
    BankExternalImportService,
    BankExportService,
    BankChallengeSubmitService,
    BankChallengeUpdateService,
    BankContextService,
)
from .schemas import (
    ProblemBankCreateSchema,
    ProblemBankUpdateSchema,
    BankImportFromContestSchema,
    BankImportChallengesSchema,
    BankExternalImportSchema,
    BankExportSchema,
    BankChallengeSubmitSchema,
    BankChallengeUpdateSchema,
)
from .repo import ProblemBankRepo, BankChallengeRepo, BankSolveRepo


class ProblemBankListView(APIView):
    """题库列表/创建：GET 登录可见公开题库，POST 管理员创建题库"""

    permission_classes = [IsAuthenticated, IsAdminOrReadOnly, BizPermission]
    biz_permission_map = {
        "get": "problem_bank.view_bank",
        "post": "problem_bank.manage_bank",
    }
    pagination_class = StandardPagination
    bank_repo = ProblemBankRepo()

    @extend_schema(
        summary="题库列表",
        operation_id="problem_bank_list",
        request=None,
        responses=list_response("ProblemBankList", problem_bank_serializer(), paginated=True),
        tags=["problem-bank"],
        parameters=pagination_parameters()
        + [
            OpenApiParameter("keyword", OpenApiTypes.STR, OpenApiParameter.QUERY, description="模糊搜索关键字（兼容旧版 search_scope）"),
            OpenApiParameter("search_scope", OpenApiTypes.STR, OpenApiParameter.QUERY, description="兼容旧版：bank/challenge/category"),
            OpenApiParameter("bank_keyword", OpenApiTypes.STR, OpenApiParameter.QUERY, description="按题库名模糊搜索"),
            OpenApiParameter("challenge_keyword", OpenApiTypes.STR, OpenApiParameter.QUERY, description="按题目名模糊搜索"),
            OpenApiParameter("category_keyword", OpenApiTypes.STR, OpenApiParameter.QUERY, description="按题目类型（分类名）模糊搜索"),
            OpenApiParameter("difficulty", OpenApiTypes.STR, OpenApiParameter.QUERY, description="难度过滤（easy/medium/hard）"),
            OpenApiParameter("tags", OpenApiTypes.STR, OpenApiParameter.QUERY, description="标签列表，逗号分隔"),
            OpenApiParameter("author", OpenApiTypes.INT, OpenApiParameter.QUERY, description="作者用户ID过滤"),
            OpenApiParameter("is_public", OpenApiTypes.BOOL, OpenApiParameter.QUERY, description="是否公开"),
            OpenApiParameter("updated_after", OpenApiTypes.DATETIME, OpenApiParameter.QUERY, description="更新时间 >= "),
            OpenApiParameter("updated_before", OpenApiTypes.DATETIME, OpenApiParameter.QUERY, description="更新时间 <="),
        ],
    )
    def get(self, request: Request) -> Response:
        qs = self.bank_repo.get_queryset()
        if not request.user.is_staff:
            qs = qs.filter(is_public=True)
        keyword = request.query_params.get("keyword") or ""
        bank_keyword = request.query_params.get("bank_keyword") or ""
        challenge_keyword = request.query_params.get("challenge_keyword") or ""
        category_keyword = request.query_params.get("category_keyword") or ""
        search_scope = (request.query_params.get("search_scope") or "bank").lower()
        # 新版：独立字段，均可叠加
        if bank_keyword:
            qs = qs.filter(models.Q(name__icontains=bank_keyword))
        if challenge_keyword:
            qs = qs.filter(models.Q(challenges__title__icontains=challenge_keyword) | models.Q(challenges__slug__icontains=challenge_keyword))
        if category_keyword:
            qs = qs.filter(
                models.Q(challenges__category__name__icontains=category_keyword)
                | models.Q(challenges__category__slug__icontains=category_keyword)
            )
        # 兼容旧版 search_scope + keyword
        if keyword:
            if search_scope == "challenge":
                qs = qs.filter(models.Q(challenges__title__icontains=keyword) | models.Q(challenges__slug__icontains=keyword))
            elif search_scope == "category":
                qs = qs.filter(
                    models.Q(challenges__category__name__icontains=keyword) | models.Q(challenges__category__slug__icontains=keyword)
                )
            else:
                qs = qs.filter(models.Q(name__icontains=keyword) | models.Q(description__icontains=keyword))
        difficulty = request.query_params.get("difficulty")
        if difficulty:
            qs = qs.filter(challenges__difficulty=difficulty)
        tags = request.query_params.get("tags", "")
        if tags:
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
            for tag in tag_list:
                qs = qs.filter(
                    models.Q(challenges__category__name__icontains=tag)
                    | models.Q(name__icontains=tag)
                    | models.Q(description__icontains=tag)
                )
        author = request.query_params.get("author")
        if author:
            qs = qs.filter(challenges__author_id=author)
        updated_after = request.query_params.get("updated_after")
        updated_before = request.query_params.get("updated_before")
        if updated_after:
            qs = qs.filter(updated_at__gte=updated_after)
        if updated_before:
            qs = qs.filter(updated_at__lte=updated_before)
        is_public = request.query_params.get("is_public")
        if is_public is not None:
            if is_public.lower() in ("true", "1"):
                qs = qs.filter(is_public=True)
            elif is_public.lower() in ("false", "0"):
                qs = qs.filter(is_public=False)
        qs = qs.distinct()
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs.order_by("-updated_at", "-created_at", "name"), request)
        items = [serialize_bank(b) for b in page]
        return paginator.get_paginated_response({"items": items})

    @extend_schema(
        summary="创建题库",
        operation_id="problem_bank_create",
        request=OpenApiTypes.OBJECT,
        responses=OpenApiTypes.OBJECT,
        tags=["problem-bank"],
        exclude=True,  # 管理员操作，不暴露给前端文档
    )
    def post(self, request: Request) -> Response:
        schema = ProblemBankCreateSchema.from_dict(request.data, auto_validate=True)
        bank = ProblemBankCreateService().execute(schema)
        return response.created({"bank": serialize_bank(bank)}, message="题库已创建")


class ProblemBankMetaView(APIView):
    """题库元信息查看/更新：GET 查看，PATCH 管理员更新"""

    permission_classes = [IsAuthenticated, IsAdminOrReadOnly, BizPermission]
    biz_permission_map = {
        "get": "problem_bank.view_bank",
        "patch": "problem_bank.manage_bank",
    }
    bank_repo = ProblemBankRepo()
    update_service = ProblemBankUpdateService()

    @extend_schema(
        summary="题库详情",
        request=None,
        responses=api_response_schema("ProblemBankDetail", {"bank": problem_bank_serializer()}),
        tags=["problem-bank"],
    )
    def get(self, request: Request, bank_slug: str) -> Response:
        _ = request
        bank = self.bank_repo.get_by_slug(bank_slug)
        return response.success({"bank": serialize_bank(bank)})

    @extend_schema(
        summary="更新题库",
        request=OpenApiTypes.OBJECT,
        responses=OpenApiTypes.OBJECT,
        tags=["problem-bank"],
        exclude=True,
    )
    def patch(self, request: Request, bank_slug: str) -> Response:
        payload = dict(request.data or {})
        payload["bank_slug"] = bank_slug
        schema = ProblemBankUpdateSchema.from_dict(payload, auto_validate=True)
        bank = self.update_service.execute(schema)
        return response.success({"bank": serialize_bank(bank)}, message="题库已更新")


class BankChallengeListView(APIView):
    """题库题目列表：需登录，可见公开题库"""

    permission_classes = [IsAuthenticated, BizPermission]
    biz_permission = "problem_bank.view_bank"
    pagination_class = StandardPagination
    context_service = BankContextService()
    challenge_repo = BankChallengeRepo()
    solve_repo = BankSolveRepo()

    @extend_schema(
        summary="题库题目列表",
        operation_id="problem_bank_challenge_list",
        request=None,
        responses=list_response("BankChallengeList", bank_challenge_serializer(), paginated=True),
        tags=["problem-bank"],
        parameters=pagination_parameters(),
    )
    def get(self, request: Request, bank_slug: str) -> Response:
        bank = self.context_service.get_bank_for_user(request.user, bank_slug)
        challenges_qs = self.challenge_repo.list_active(bank=bank)
        category = request.query_params.get("category")
        if category:
            challenges_qs = challenges_qs.filter(
                models.Q(category__slug=category) | models.Q(category__name__iexact=category)
            )
        challenges = challenges_qs.order_by("slug")
        solved_ids = set(
            self.solve_repo.filter(challenge__bank=bank, user=request.user).values_list("challenge_id", flat=True)
        )
        paginator = StandardPagination()
        page = paginator.paginate_queryset(challenges, request)
        data = [serialize_challenge(ch, solved=ch.id in solved_ids, request=request) for ch in page]
        # 收集所有分类（用于前端筛选，不随分页丢失）
        all_categories = (
            self.challenge_repo.list_active(bank=bank)
            .exclude(category__isnull=True)
            .values_list("category__slug", "category__name")
            .distinct()
        )
        categories = [{"slug": slug or "", "name": name or ""} for slug, name in all_categories]
        return page_success(
            items={"items": data, "categories": categories},
            page=paginator.page.number,
            page_size=paginator.get_page_size(request) or paginator.page.paginator.per_page,
            total=paginator.page.paginator.count,
            has_next=paginator.page.has_next(),
            has_previous=paginator.page.has_previous(),
            total_pages=paginator.page.paginator.num_pages,
            next_page=paginator.page.next_page_number() if paginator.page.has_next() else None,
            previous_page=paginator.page.previous_page_number() if paginator.page.has_previous() else None,
        )


class BankChallengeDetailView(APIView):
    """题库题目详情：需登录"""

    permission_classes = [IsAuthenticated, IsAdminOrReadOnly, BizPermission]
    biz_permission_map = {
        "get": "problem_bank.view_bank",
        "patch": "problem_bank.manage_bank_challenge",
    }
    context_service = BankContextService()
    challenge_repo = BankChallengeRepo()
    solve_repo = BankSolveRepo()
    update_service = BankChallengeUpdateService()

    @extend_schema(
        summary="题库题目详情",
        operation_id="problem_bank_challenge_detail",
        request=None,
        responses=api_response_schema(
            "BankChallengeDetail",
            {"challenge": bank_challenge_serializer()},
        ),
        tags=["problem-bank"],
    )
    def get(self, request: Request, bank_slug: str, challenge_slug: str) -> Response:
        bank = self.context_service.get_bank_for_user(request.user, bank_slug)
        challenge = self.challenge_repo.get_by_slug(bank=bank, slug=challenge_slug)
        solved = self.solve_repo.has_solved(challenge=challenge, user=request.user)
        return response.success({"challenge": serialize_challenge(challenge, solved=solved, request=request)})

    @extend_schema(
        summary="更新题库题目",
        operation_id="problem_bank_challenge_update",
        request=OpenApiTypes.OBJECT,
        responses=OpenApiTypes.OBJECT,
        tags=["problem-bank"],
        exclude=True,
    )
    def patch(self, request: Request, bank_slug: str, challenge_slug: str) -> Response:
        payload = dict(request.data or {})
        payload.update({"bank_slug": bank_slug, "challenge_slug": challenge_slug})
        schema = BankChallengeUpdateSchema.from_dict(payload, auto_validate=True)
        challenge = self.update_service.execute(schema)
        return response.success({"challenge": serialize_challenge(challenge, request=request)}, message="题目已更新")


class BankChallengeSubmitView(APIView):
    """题库作答：需登录，不计分，仅记录解题状态"""

    permission_classes = [IsAuthenticated, BizPermission]
    biz_permission = "problem_bank.submit_bank_flag"
    service = BankChallengeSubmitService()

    @extend_schema(
        summary="题库内提交 Flag",
        request=inline_serializer(
            name="BankSubmitRequest",
            fields={"flag": serializers.CharField(help_text="提交的 Flag")},
        ),
        responses=api_response_schema(
            "BankSubmit",
            {"solved_at": serializers.DateTimeField(help_text="解题时间")},
        ),
        tags=["submissions"],
    )
    def post(self, request: Request, bank_slug: str, challenge_slug: str) -> Response:
        schema = BankChallengeSubmitSchema.from_dict(request.data, auto_validate=True)
        solve = self.service.execute(request.user, bank_slug, challenge_slug, schema)
        return response.success({"solved_at": solve.solved_at}, message="提交正确")


class BankImportFromContestView(APIView):
    """从比赛导入全部题目到题库：管理员"""

    permission_classes = [IsAdmin, BizPermission]
    biz_permission = "problem_bank.import_bank"
    service = BankImportFromContestService()

    @extend_schema(
        summary="从比赛导入全部题目",
        request=OpenApiTypes.OBJECT,
        responses=OpenApiTypes.OBJECT,
        tags=["problem-bank"],
        exclude=True,
    )
    def post(self, request: Request, bank_slug: str) -> Response:
        payload = dict(request.data)
        payload["bank_slug"] = bank_slug
        schema = BankImportFromContestSchema.from_dict(payload, auto_validate=True)
        imported = self.service.execute(schema)
        return response.success({"count": len(imported)}, message="已导入题目")


class BankImportChallengesView(APIView):
    """从比赛导入指定题目到题库：管理员"""

    permission_classes = [IsAdmin, BizPermission]
    biz_permission = "problem_bank.import_bank"
    service = BankImportChallengesService()

    @extend_schema(
        summary="从比赛导入指定题目",
        request=OpenApiTypes.OBJECT,
        responses=OpenApiTypes.OBJECT,
        tags=["problem-bank"],
        exclude=True,
    )
    def post(self, request: Request, bank_slug: str) -> Response:
        payload = dict(request.data)
        payload["bank_slug"] = bank_slug
        schema = BankImportChallengesSchema.from_dict(payload, auto_validate=True)
        imported = self.service.execute(schema)
        return response.success({"count": len(imported)}, message="已导入题目")


class BankExternalImportView(APIView):
    """外部 zip 导入题库：管理员"""

    permission_classes = [IsAdmin, BizPermission]
    biz_permission = "problem_bank.import_bank"
    parser_classes = []  # 具体上传由前端控制，可复用附件上传服务，预留表单/文件解析
    service = BankExternalImportService()

    @extend_schema(
        summary="外部 zip 导入题库",
        request=OpenApiTypes.OBJECT,
        responses=OpenApiTypes.OBJECT,
        tags=["problem-bank"],
        exclude=True,
    )
    def post(self, request: Request, bank_slug: str) -> Response:
        # 功能占位，尚未开放外部 zip 导入
        raise ValidationError(message="外部导入暂未开放，请使用比赛导入或后台录入")


class BankExportView(APIView):
    """导出题库 zip：管理员"""

    permission_classes = [IsAdmin, BizPermission]
    biz_permission = "problem_bank.export_bank"
    service = BankExportService()

    @extend_schema(
        summary="导出题库",
        request=None,
        responses=OpenApiTypes.OBJECT,
        tags=["problem-bank"],
        exclude=True,
    )
    def get(self, request: Request, bank_slug: str) -> Response:
        _ = request
        schema = BankExportSchema(bank_slug=bank_slug)
        result = self.service.execute(schema)
        encoded = base64.b64encode(result["content"]).decode("ascii")
        return response.success(
            {"filename": result["filename"], "content_base64": encoded},
            message="导出成功",
        )
