from __future__ import annotations

from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from drf_spectacular.types import OpenApiTypes

from apps.common import response
from apps.common.permissions import IsAuthenticated, BizPermission
from apps.common.throttles import FlagSubmitRateThrottle
from apps.challenges.serializers import serialize_challenge

from .schemas import SubmissionCreateSchema
from .services import SubmissionService, serialize_submission


# 视图层：提供提交接口，记录提交并走统一判题逻辑


class SubmissionCreateView(APIView):
    """
    Flag 提交接口：
    - 需登录，校验比赛状态与题目开放性
    - 正确返回解题记录，错误也会落库提交记录
    """

    permission_classes = [IsAuthenticated, BizPermission]
    biz_permission = "challenges.submit_contest_flag"
    throttle_classes = [FlagSubmitRateThrottle]
    service = SubmissionService()

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request) -> Response:
        # Schema 校验入参后，调用服务完成判题与记录
        schema = SubmissionCreateSchema.from_dict(request.data, auto_validate=True)
        submission = self.service.execute(request.user, schema)
        base_points = max(0, submission.awarded_points - getattr(submission, "bonus_points", 0))
        challenge_payload = serialize_challenge(submission.challenge, current_points=base_points, request=request)
        return response.created(
            {
                "submission": serialize_submission(submission),
                "challenge": challenge_payload,
                "awarded_points": submission.awarded_points,
                "bonus_points": getattr(submission, "bonus_points", 0),
                "solved_at": getattr(submission.solve, "solved_at", None),
            },
            message="提交已记录",
        )
