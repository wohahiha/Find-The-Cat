from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from drf_spectacular.types import OpenApiTypes

from apps.common import response
from apps.common.permissions import IsAdmin

from .schemas import ChallengeCreateSchema, ChallengeUpdateSchema, ChallengeSubmitSchema
from .services import (
    ChallengeCreateService,
    ChallengeUpdateService,
    ChallengeSubmitService,
    serialize_challenge,
)
from apps.contests.services import ContestContextService
from .repo import ChallengeRepo

# 视图层：提供题目列表/创建、详情/更新、提交 Flag 的接口。仅做参数转换与服务调用。


class ChallengeListView(APIView):
    """题目列表/创建接口：GET 需登录，POST 需管理员。"""
    permission_classes = [IsAuthenticated]
    context_service = ContestContextService()
    challenge_repo = ChallengeRepo()

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    def get(self, request: Request, contest_slug: str) -> Response:
        # 获取比赛并返回所有已开放题目
        contest = self.context_service.get_contest(contest_slug)
        challenges = self.challenge_repo.filter(contest=contest, is_active=True)
        data = [serialize_challenge(ch) for ch in challenges]
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
    """题目详情/更新接口：GET 需登录，PATCH 需管理员。"""
    permission_classes = [IsAuthenticated]
    context_service = ContestContextService()
    challenge_repo = ChallengeRepo()

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    def get(self, request: Request, contest_slug: str, challenge_slug: str) -> Response:
        # 获取题目并返回详情
        contest = self.context_service.get_contest(contest_slug)
        challenge = self.challenge_repo.get_by_slug(contest=contest, slug=challenge_slug)
        return response.success({"challenge": serialize_challenge(challenge)})

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


class ChallengeSubmitView(APIView):
    """提交 Flag 接口：需登录，校验后返回得分。"""
    permission_classes = [IsAuthenticated]

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request, contest_slug: str, challenge_slug: str) -> Response:
        # 校验入参并调用提交服务
        schema = ChallengeSubmitSchema.from_dict(request.data, auto_validate=True)
        solve = ChallengeSubmitService().execute(
            request.user,
            contest_slug=contest_slug,
            challenge_slug=challenge_slug,
            schema=schema,
        )
        return response.success(
            {
                "challenge": serialize_challenge(solve.challenge),
                "awarded_points": solve.awarded_points,
                "solved_at": solve.solved_at,
            },
            message="恭喜，Flag 正确！",
        )
