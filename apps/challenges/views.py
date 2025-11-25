from __future__ import annotations

from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from drf_spectacular.utils import extend_schema
from drf_spectacular.types import OpenApiTypes

from apps.common import response
from apps.common.permissions import IsAdmin, IsAuthenticated

from .schemas import ChallengeCreateSchema, ChallengeUpdateSchema, HintUnlockSchema
from .services import ChallengeCreateService, ChallengeUpdateService, ChallengeHintService, AttachmentUploadService
from .serializers import serialize_challenge
from apps.contests.services import ContestContextService
from .repo import ChallengeRepo
from .schemas import AttachmentUploadSchema
from apps.submissions.services import SubmissionService

# 视图层：提供题目列表/创建、详情/更新、提交 Flag 的接口。仅做参数转换与服务调用。


class ChallengeListView(APIView):
    """题目列表/创建接口：GET 需登录查看，POST 需管理员创建。"""
    permission_classes = [IsAuthenticated]
    context_service = ContestContextService()
    challenge_repo = ChallengeRepo()
    hint_service = ChallengeHintService()
    submit_service = SubmissionService()

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    def get(self, request: Request, contest_slug: str) -> Response:
        # 获取比赛并返回所有已开放题目，计算当前用户可得分（动态计分+提示扣分）
        contest = self.context_service.get_contest(contest_slug)
        challenges = self.challenge_repo.filter(contest=contest, is_active=True)
        membership = self.submit_service.member_repo.get_membership(contest=contest, user=request.user)
        data = [
            serialize_challenge(
                ch,
                current_points=self.submit_service.visible_points_for_user(
                    request.user, contest, ch, membership=membership
                ),
            )
            for ch in challenges
        ]
        return response.success({"items": data})

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request, contest_slug: str) -> Response:
        # 运行时切换权限为管理员
        self.permission_classes = [IsAdmin]  # type: ignore[assignment]
        # 补充比赛标识后创建题目
        payload = dict(request.data)
        payload["contest_slug"] = contest_slug
        schema = ChallengeCreateSchema.from_dict(payload, auto_validate=True)
        challenge = ChallengeCreateService().execute(request.user, schema)
        return response.created({"challenge": serialize_challenge(challenge)}, message="题目已创建")


class ChallengeDetailView(APIView):
    """题目详情/更新接口：GET 需登录查看，PATCH 需管理员更新。"""
    permission_classes = [IsAuthenticated]
    context_service = ContestContextService()
    challenge_repo = ChallengeRepo()
    submit_service = SubmissionService()

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    def get(self, request: Request, contest_slug: str, challenge_slug: str) -> Response:
        # 获取题目并返回详情，附带当前可得分（动态计分+提示扣分）
        contest = self.context_service.get_contest(contest_slug)
        challenge = self.challenge_repo.get_by_slug(contest=contest, slug=challenge_slug)
        membership = self.submit_service.member_repo.get_membership(contest=contest, user=request.user)
        return response.success(
            {
                "challenge": serialize_challenge(
                    challenge,
                    current_points=self.submit_service.visible_points_for_user(
                        request.user, contest, challenge, membership=membership
                    ),
                )
            }
        )

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def patch(self, request: Request, contest_slug: str, challenge_slug: str) -> Response:
        # 运行时切换权限为管理员
        self.permission_classes = [IsAdmin]  # type: ignore[assignment]
        # 补充比赛/题目标识后更新题目
        payload = dict(request.data)
        payload.update({"contest_slug": contest_slug, "slug": challenge_slug})
        schema = ChallengeUpdateSchema.from_dict(payload, auto_validate=True)
        challenge = ChallengeUpdateService().execute(schema)
        return response.success({"challenge": serialize_challenge(challenge)}, message="题目已更新")


class ChallengeHintListView(APIView):
    """题目提示列表：需登录，未解锁提示不返回内容。"""
    permission_classes = [IsAuthenticated]
    hint_service = ChallengeHintService()

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    def get(self, request: Request, contest_slug: str, challenge_slug: str) -> Response:
        hints = self.hint_service.execute(
            request.user,
            action="list",
            contest_slug=contest_slug,
            challenge_slug=challenge_slug,
        )
        return response.success({"items": hints})


class ChallengeHintUnlockView(APIView):
    """解锁提示：需登录，扣分提示需先解锁。"""
    permission_classes = [IsAuthenticated]
    hint_service = ChallengeHintService()

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request, contest_slug: str, challenge_slug: str, hint_id: int) -> Response:
        schema = HintUnlockSchema.from_dict(request.data or {}, auto_validate=True)
        hint = self.hint_service.execute(
            request.user,
            action="unlock",
            contest_slug=contest_slug,
            challenge_slug=challenge_slug,
            hint_id=hint_id,
            schema=schema,
        )
        return response.success({"hint": hint}, message="提示已解锁")


class AttachmentUploadView(APIView):
    """
    题目附件上传接口：仅管理员可用，返回存储路径与 URL。
    - 支持可选 contest_slug/challenge_slug 归档子目录。
    """

    permission_classes = [IsAuthenticated, IsAdmin]
    parser_classes = [MultiPartParser, FormParser]
    service = AttachmentUploadService()

    @extend_schema(
        summary="上传题目附件",
        description="管理员上传附件文件，返回存储路径与访问 URL（仅保存元信息，不包含文件内容）。",
        request=OpenApiTypes.OBJECT,
        responses=OpenApiTypes.OBJECT,
    )
    def post(self, request: Request, contest_slug: str) -> Response:
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return response.fail(message="请上传文件", code=40002)
        schema = AttachmentUploadSchema.from_dict(
            {
                "contest_slug": contest_slug or request.data.get("contest_slug"),
                "challenge_slug": request.data.get("challenge_slug"),
                "filename": uploaded_file.name,
            },
            auto_validate=True,
        )
        result = self.service.execute(schema, content=uploaded_file.read())
        return response.success({"attachment": result}, message="附件已上传")
