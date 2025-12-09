from __future__ import annotations

from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer
from drf_spectacular.types import OpenApiTypes
from rest_framework import serializers

from apps.common import response
from apps.common.permissions import BizPermission, IsAdmin, IsAuthenticated
from apps.common.throttles import AttachmentUploadRateThrottle
from apps.common.schema_utils import (
    api_response_schema,
    list_response,
    challenge_summary_serializer,
    hint_serializer,
)
from apps.common.exceptions import NotFoundError
from apps.common.infra.logger import get_logger, logger_extra
from apps.common.utils.validators import validate_upload_file

from .schemas import ChallengeCreateSchema, ChallengeUpdateSchema, HintUnlockSchema
from .services import ChallengeCreateService, ChallengeUpdateService, ChallengeHintService, AttachmentUploadService
from .serializers import serialize_challenge
from apps.contests.services import ContestContextService
from .repo import ChallengeRepo
from .schemas import AttachmentUploadSchema
from apps.submissions.services import SubmissionService

# 模块级日志
logger = get_logger(__name__)


# 视图层：提供题目列表/创建、详情/更新、提交 Flag 的接口仅做参数转换与服务调用


@extend_schema_view(
    get=extend_schema(tags=["challenges"]),
    post=extend_schema(tags=["challenges"]),
)
class ChallengeListView(APIView):
    """题目列表/创建接口：GET 需登录查看，POST 需管理员创建"""
    permission_classes = [IsAuthenticated, BizPermission]
    biz_permission_map = {
        "get": "challenges.view_contest_challenge",
        "post": "challenges.manage_contest_challenge",
    }
    context_service = ContestContextService()
    challenge_repo = ChallengeRepo()
    hint_service = ChallengeHintService()
    submit_service = SubmissionService()

    @extend_schema(
        summary="题目列表",
        operation_id="challenge_list",
        request=None,
        responses=list_response(
            "ChallengeList",
            challenge_summary_serializer(),
        ),
    )
    def get(self, request: Request, contest_slug: str) -> Response:
        # 获取比赛并返回所有已开放题目，计算当前用户可得分（动态计分+提示扣分）
        contest = self.context_service.get_contest(contest_slug)
        self.context_service.ensure_contest_visible(contest, request.user)
        self.context_service.ensure_contest_started(contest)
        challenges = self.challenge_repo.list_active_with_related(contest=contest)
        membership = self.submit_service.member_repo.get_membership(contest=contest, user=request.user)
        data = [
            serialize_challenge(
                ch,
                current_points=self.submit_service.visible_points_for_user(
                    request.user, contest, ch, membership=membership
                ),
                request=request,
            )
            for ch in challenges
        ]
        return response.success({"items": data})

    @extend_schema(
        summary="创建题目",
        operation_id="challenge_create",
        request=OpenApiTypes.OBJECT,
        responses=OpenApiTypes.OBJECT,
        exclude=True,  # 管理员专用，前端不展示
    )
    def post(self, request: Request, contest_slug: str) -> Response:
        # 补充比赛标识后创建题目
        payload = dict(request.data)
        payload["contest_slug"] = contest_slug
        schema = ChallengeCreateSchema.from_dict(payload, auto_validate=True)
        challenge = ChallengeCreateService().execute(request.user, schema)
        return response.created({"challenge": serialize_challenge(challenge, request=request)}, message="题目已创建")


@extend_schema_view(
    get=extend_schema(tags=["challenges"]),
    patch=extend_schema(tags=["challenges"]),
)
class ChallengeDetailView(APIView):
    """题目详情/更新接口：GET 需登录查看，PATCH 需管理员更新"""
    permission_classes = [IsAuthenticated, BizPermission]
    biz_permission_map = {
        "get": "challenges.view_contest_challenge",
        "patch": "challenges.manage_contest_challenge",
    }
    context_service = ContestContextService()
    challenge_repo = ChallengeRepo()
    submit_service = SubmissionService()

    @extend_schema(
        summary="题目详情",
        operation_id="challenge_detail",
        request=None,
        responses=api_response_schema(
            "ChallengeDetail",
            {
                "challenge": challenge_summary_serializer(),
            },
        ),
    )
    def get(self, request: Request, contest_slug: str, challenge_slug: str) -> Response:
        # 获取题目并返回详情，附带当前可得分（动态计分+提示扣分）
        contest = self.context_service.get_contest(contest_slug)
        self.context_service.ensure_contest_visible(contest, request.user)
        self.context_service.ensure_contest_started(contest)
        challenge = self.challenge_repo.get_by_slug(contest=contest, slug=challenge_slug)
        membership = self.submit_service.member_repo.get_membership(contest=contest, user=request.user)
        return response.success(
            {
                "challenge": serialize_challenge(
                    challenge,
                    current_points=self.submit_service.visible_points_for_user(
                        request.user, contest, challenge, membership=membership
                    ),
                    request=request,
                )
            }
        )

    @extend_schema(
        summary="更新题目",
        operation_id="challenge_update",
        request=OpenApiTypes.OBJECT,
        responses=OpenApiTypes.OBJECT,
        exclude=True,  # 管理员专用
    )
    def patch(self, request: Request, contest_slug: str, challenge_slug: str) -> Response:
        # 补充比赛/题目标识后更新题目
        payload = dict(request.data)
        payload.update({"contest_slug": contest_slug, "slug": challenge_slug})
        schema = ChallengeUpdateSchema.from_dict(payload, auto_validate=True)
        challenge = ChallengeUpdateService().execute(schema)
        return response.success({"challenge": serialize_challenge(challenge, request=request)}, message="题目已更新")


# 嵌套在 contests 下的接口（用于生成唯一 operation_id 与摘要）




@extend_schema_view(get=extend_schema(tags=["challenges"]))
class ChallengeHintListView(APIView):
    """题目提示列表：需登录，未解锁提示不返回内容"""
    permission_classes = [IsAuthenticated, BizPermission]
    biz_permission = "challenges.view_contest_challenge"
    hint_service = ChallengeHintService()

    @extend_schema(
        summary="提示列表",
        request=None,
        responses=list_response("ChallengeHintList", hint_serializer()),
    )
    def get(self, request: Request, contest_slug: str, challenge_slug: str) -> Response:
        hints = self.hint_service.execute(
            request.user,
            action="list",
            contest_slug=contest_slug,
            challenge_slug=challenge_slug,
        )
        return response.success({"items": hints})


@extend_schema_view(post=extend_schema(tags=["challenges"]))
class ChallengeHintUnlockView(APIView):
    """解锁提示：需登录，扣分提示需先解锁"""
    permission_classes = [IsAuthenticated, BizPermission]
    biz_permission = "challenges.view_contest_challenge"
    hint_service = ChallengeHintService()

    @extend_schema(
        summary="解锁提示",
        request=None,
        responses=api_response_schema("ChallengeHintUnlock", {"hint": hint_serializer()}),
    )
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


@extend_schema_view(post=extend_schema(tags=["challenges"]))
class AttachmentUploadView(APIView):
    """
    题目附件上传接口：仅管理员可用，返回存储路径与 URL
    - 支持可选 contest_slug/challenge_slug 归档子目录
    """

    permission_classes = [IsAuthenticated, IsAdmin, BizPermission]
    biz_permission = "challenges.manage_contest_attachment"
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [AttachmentUploadRateThrottle]
    service = AttachmentUploadService()

    @extend_schema(
        summary="上传题目附件",
        description="管理员上传附件文件，返回存储路径与访问 URL（仅保存元信息，不包含文件内容，需 challenges.manage_contest_attachment 权限）",
        request=inline_serializer(
            name="AttachmentUploadRequest",
            fields={
                "file": serializers.FileField(help_text="附件文件（zip/tar/gz/7z/txt/pdf/md/json，10MB 内）"),
                "challenge_slug": serializers.CharField(required=False, allow_blank=True, help_text="可选题目标识"),
            },
        ),
        responses=api_response_schema(
            "AttachmentUpload",
            {
                "attachment": inline_serializer(
                    name="AttachmentInfo",
                    fields={
                        "path": serializers.CharField(help_text="存储相对路径"),
                        "url": serializers.CharField(help_text="附件访问 URL"),
                    },
                )
            },
        ),
    )
    def post(self, request: Request, contest_slug: str) -> Response:
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return response.fail(message="请上传文件", code=40002)
        validate_upload_file(
            uploaded_file,
            allowed_content_types={
                "application/zip",
                "application/x-zip-compressed",
                "application/gzip",
                "application/x-gzip",
                "application/x-7z-compressed",
                "application/x-tar",
                "application/x-bzip2",
                "application/octet-stream",
                "application/json",
                "text/plain",
                "application/pdf",
            },
            allowed_suffixes={".zip", ".tar", ".gz", ".tgz", ".bz2", ".7z", ".txt", ".pdf", ".md", ".json"},
            max_size_mb=10,
            field_name="附件",
        )
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


# 嵌套在 contests 下的接口（用于生成唯一 operation_id 与摘要）


class ContestChallengeListView(ChallengeListView):
    """比赛下的题目列表/创建接口"""

    @extend_schema(
        summary="题目列表（按比赛）",
        operation_id="contest_challenges_list",
        request=None,
        responses=list_response(
            "ContestChallengeList",
            challenge_summary_serializer(),
        ),
        tags=["challenges"],
    )
    def get(self, request: Request, contest_slug: str) -> Response:
        return super().get(request, contest_slug)

    @extend_schema(
        summary="创建题目（按比赛）",
        operation_id="contest_challenge_create",
        request=OpenApiTypes.OBJECT,
        responses=OpenApiTypes.OBJECT,
        tags=["challenges"],
        exclude=True,
    )
    def post(self, request: Request, contest_slug: str) -> Response:
        return super().post(request, contest_slug)


class ContestChallengeDetailView(ChallengeDetailView):
    """比赛下的题目详情/更新接口"""

    @extend_schema(
        summary="题目详情（按比赛）",
        operation_id="contest_challenge_detail",
        request=None,
        responses=api_response_schema(
            "ContestChallengeDetail",
            {"challenge": challenge_summary_serializer()},
        ),
        tags=["challenges"],
    )
    def get(self, request: Request, contest_slug: str, challenge_slug: str) -> Response:
        return super().get(request, contest_slug, challenge_slug)

    @extend_schema(
        summary="更新题目（按比赛）",
        operation_id="contest_challenge_update",
        request=OpenApiTypes.OBJECT,
        responses=OpenApiTypes.OBJECT,
        tags=["challenges"],
        exclude=True,
    )
    def patch(self, request: Request, contest_slug: str, challenge_slug: str) -> Response:
        return super().patch(request, contest_slug, challenge_slug)


class ContestChallengeHintListView(ChallengeHintListView):
    """比赛下的题目提示列表"""

    @extend_schema(
        summary="提示列表（按比赛）",
        operation_id="contest_challenge_hint_list",
        request=None,
        responses=list_response("ChallengeHintList", hint_serializer()),
        tags=["challenges"],
    )
    def get(self, request: Request, contest_slug: str, challenge_slug: str) -> Response:
        return super().get(request, contest_slug, challenge_slug)


class ContestChallengeHintUnlockView(ChallengeHintUnlockView):
    """比赛下的题目提示解锁"""

    @extend_schema(
        summary="解锁提示（按比赛）",
        operation_id="contest_challenge_hint_unlock",
        request=OpenApiTypes.OBJECT,
        responses=api_response_schema("ChallengeHintUnlock", {"hint": hint_serializer()}),
        tags=["challenges"],
    )
    def post(self, request: Request, contest_slug: str, challenge_slug: str, hint_id: int) -> Response:
        return super().post(request, contest_slug, challenge_slug, hint_id)


class ContestAttachmentUploadView(AttachmentUploadView):
    """比赛下的题目附件上传"""

    @extend_schema(
        summary="上传题目附件",
        operation_id="contest_challenge_attachment_upload",
        description="管理员上传题目附件（需 challenges.manage_contest_attachment 权限）",
        request=inline_serializer(
            name="ContestAttachmentUploadRequest",
            fields={
                "file": serializers.FileField(help_text="附件文件（zip/tar/gz/7z/txt/pdf/md/json，10MB 内）"),
                "challenge_slug": serializers.CharField(required=False, allow_blank=True, help_text="可选题目标识"),
            },
        ),
        responses=api_response_schema(
            "ContestAttachmentUpload",
            {
                "attachment": inline_serializer(
                    name="AttachmentInfo",
                    fields={
                        "path": serializers.CharField(help_text="存储相对路径"),
                        "url": serializers.CharField(help_text="附件访问 URL"),
                    },
                )
            },
        ),
        tags=["challenges"],
    )
    def post(self, request: Request, contest_slug: str) -> Response:
        return super().post(request, contest_slug)


class ChallengeAttachmentDownloadView(APIView):
    """题目附件下载：需登录，返回附件下载 URL"""

    permission_classes = [IsAuthenticated, BizPermission]
    biz_permission = "challenges.download_contest_attachment"
    challenge_repo = ChallengeRepo()

    @extend_schema(
        summary="下载题目附件",
        request=None,
        responses=api_response_schema(
            "ChallengeAttachmentDownload",
            {
                "name": serializers.CharField(help_text="附件名称"),
                "url": serializers.CharField(help_text="附件下载 URL"),
            },
        ),
        tags=["challenges"],
    )
    def get(self, request: Request, contest_slug: str, challenge_slug: str, attachment_id: int) -> Response:
        # 校验题目存在
        context_service = ContestContextService()
        contest = context_service.get_contest(contest_slug)
        context_service.ensure_contest_visible(contest, request.user)
        context_service.ensure_contest_started(contest)
        challenge = self.challenge_repo.get_by_slug(contest=contest, slug=challenge_slug)
        attachment = challenge.attachments.filter(id=attachment_id).first()  # type: ignore[attr-defined]
        if not attachment:
            raise NotFoundError(message="附件不存在")
        logger.info(
            "下载题目附件",
            extra=logger_extra(
                {
                    "contest": contest.slug,
                    "challenge": challenge.slug,
                    "attachment_id": attachment_id,
                    "user_id": request.user.id,
                }
            ),
        )
        return response.success({"name": attachment.name, "url": attachment.url}, message="获取附件链接")
