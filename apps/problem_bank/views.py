from __future__ import annotations

from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from drf_spectacular.types import OpenApiTypes
import base64

from apps.common import response
from apps.common.permissions import IsAuthenticated, IsAdmin, AllowAny

from .serializers import serialize_bank, serialize_challenge
from .services import (
    ProblemBankCreateService,
    BankImportFromContestService,
    BankImportChallengesService,
    BankExternalImportService,
    BankExportService,
    BankChallengeSubmitService,
)
from .schemas import (
    ProblemBankCreateSchema,
    BankImportFromContestSchema,
    BankImportChallengesSchema,
    BankExternalImportSchema,
    BankExportSchema,
    BankChallengeSubmitSchema,
)
from .repo import ProblemBankRepo, BankChallengeRepo, BankSolveRepo


class ProblemBankListView(APIView):
    """题库列表/创建：GET 登录可见公开题库，POST 管理员创建题库"""

    permission_classes = [IsAuthenticated]
    bank_repo = ProblemBankRepo()

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    def get(self, request: Request) -> Response:
        qs = self.bank_repo.get_queryset()
        if not request.user.is_staff:
            qs = qs.filter(is_public=True)
        items = [serialize_bank(b) for b in qs.order_by("-created_at", "name")]
        return response.success({"items": items})

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request) -> Response:
        self.permission_classes = [IsAdmin]  # type: ignore[assignment]
        schema = ProblemBankCreateSchema.from_dict(request.data, auto_validate=True)
        bank = ProblemBankCreateService().execute(schema)
        return response.created({"bank": serialize_bank(bank)}, message="题库已创建")


class BankChallengeListView(APIView):
    """题库题目列表：需登录，可见公开题库"""

    permission_classes = [IsAuthenticated]
    bank_repo = ProblemBankRepo()
    challenge_repo = BankChallengeRepo()
    solve_repo = BankSolveRepo()

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    def get(self, request: Request, bank_slug: str) -> Response:
        try:
            bank = self.bank_repo.get_by_slug(bank_slug)
        except Exception:
            try:
                bank = self.bank_repo.get_by_id(int(bank_slug))
            except Exception:
                return response.fail(code=40400, message="题库不存在", http_status=404)
        if not bank.is_public and not request.user.is_staff:
            return response.fail(code=40300, message="题库未公开", http_status=403)
        challenges = self.challenge_repo.list_active(bank=bank)
        solved_ids = set(
            self.solve_repo.filter(challenge__bank=bank, user=request.user).values_list("challenge_id", flat=True)
        )
        data = [serialize_challenge(ch, solved=ch.id in solved_ids) for ch in challenges]
        return response.success({"items": data})


class BankChallengeDetailView(APIView):
    """题库题目详情：需登录"""

    permission_classes = [IsAuthenticated]
    bank_repo = ProblemBankRepo()
    challenge_repo = BankChallengeRepo()
    solve_repo = BankSolveRepo()

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    def get(self, request: Request, bank_slug: str, challenge_slug: str) -> Response:
        try:
            bank = self.bank_repo.get_by_slug(bank_slug)
        except Exception:
            try:
                bank = self.bank_repo.get_by_id(int(bank_slug))
            except Exception:
                return response.fail(code=40400, message="题库不存在", http_status=404)
        if not bank.is_public and not request.user.is_staff:
            return response.fail(code=40300, message="题库未公开", http_status=403)
        challenge = self.challenge_repo.get_by_slug(bank=bank, slug=challenge_slug)
        solved = self.solve_repo.has_solved(challenge=challenge, user=request.user)
        return response.success({"challenge": serialize_challenge(challenge, solved=solved)})


class BankChallengeSubmitView(APIView):
    """题库作答：需登录，不计分，仅记录解题状态"""

    permission_classes = [IsAuthenticated]
    service = BankChallengeSubmitService()

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request, bank_slug: str, challenge_slug: str) -> Response:
        schema = BankChallengeSubmitSchema.from_dict(request.data, auto_validate=True)
        solve = self.service.execute(request.user, bank_slug, challenge_slug, schema)
        return response.success({"solved_at": solve.solved_at}, message="提交正确")


class BankImportFromContestView(APIView):
    """从比赛导入全部题目到题库：管理员"""

    permission_classes = [IsAdmin]
    service = BankImportFromContestService()

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request, bank_slug: str) -> Response:
        payload = dict(request.data)
        payload["bank_slug"] = bank_slug
        schema = BankImportFromContestSchema.from_dict(payload, auto_validate=True)
        imported = self.service.execute(schema)
        return response.success({"count": len(imported)}, message="已导入题目")


class BankImportChallengesView(APIView):
    """从比赛导入指定题目到题库：管理员"""

    permission_classes = [IsAdmin]
    service = BankImportChallengesService()

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request, bank_slug: str) -> Response:
        payload = dict(request.data)
        payload["bank_slug"] = bank_slug
        schema = BankImportChallengesSchema.from_dict(payload, auto_validate=True)
        imported = self.service.execute(schema)
        return response.success({"count": len(imported)}, message="已导入题目")


class BankExternalImportView(APIView):
    """外部 zip 导入题库：管理员"""

    permission_classes = [IsAdmin]
    parser_classes = []  # 具体上传由前端控制，可复用附件上传服务
    service = BankExternalImportService()

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request, bank_slug: str) -> Response:
        uploaded = request.FILES.get("file")
        if not uploaded:
            return response.fail(code=40002, message="请上传文件")
        schema = BankExternalImportSchema.from_dict(
            {"bank_slug": bank_slug, "filename": uploaded.name},
            auto_validate=True,
        )
        items = self.service.execute(schema, content=uploaded.read())
        return response.success({"count": len(items)}, message="导入成功")


class BankExportView(APIView):
    """导出题库 zip：管理员"""

    permission_classes = [IsAdmin]
    service = BankExportService()

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    def get(self, request: Request, bank_slug: str) -> Response:
        schema = BankExportSchema(bank_slug=bank_slug)
        result = self.service.execute(schema)
        encoded = base64.b64encode(result["content"]).decode("ascii")
        return response.success(
            {"filename": result["filename"], "content_base64": encoded},
            message="导出成功",
        )
