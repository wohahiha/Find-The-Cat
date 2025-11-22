from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common import response

from .schemas import SubmissionCreateSchema
from .services import SubmissionService, serialize_submission

# 视图层：提供提交接口，记录提交并走统一判题逻辑。


class SubmissionCreateView(APIView):
    """
    Flag 提交接口：
    - 需登录，校验比赛状态与题目开放性。
    - 正确返回解题记录，错误也会落库提交记录。
    """

    permission_classes = [IsAuthenticated]
    service = SubmissionService()

    def post(self, request: Request) -> Response:
        schema = SubmissionCreateSchema.from_dict(request.data, auto_validate=True)
        submission = self.service.execute(request.user, schema)
        return response.created(
            {"submission": serialize_submission(submission)},
            message="提交已记录",
        )
