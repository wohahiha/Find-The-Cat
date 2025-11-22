from __future__ import annotations

from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common import response
from apps.common.permissions import IsAuthenticated, IsAdmin
from apps.challenges.repo import ChallengeRepo
from apps.challenges.services import serialize_challenge

from .repo import ContestRepo, TeamRepo, TeamMemberRepo
from .services import (
    ContestContextService,
    ScoreboardService,
    ContestAnnouncementService,
    TeamInviteResetService,
    TeamTransferService,
    serialize_announcement,
)
from .schemas import (
    ContestCreateSchema,
    TeamCreateSchema,
    TeamJoinSchema,
    TeamLeaveSchema,
    TeamDisbandSchema,
    AnnouncementCreateSchema,
    TeamInviteResetSchema,
    TeamTransferSchema,
)
from .services import (
    CreateContestService,
    TeamCreateService,
    TeamJoinService,
    TeamLeaveService,
    TeamDisbandService,
    serialize_contest,
    serialize_team,
)

# 视图层：暴露比赛、公告、队伍接口，仅做参数转换与调用服务层，不承载业务。


class ContestListView(APIView):
    """比赛列表/创建接口：GET 公共访问，POST 仅管理员。"""
    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        # 按状态过滤比赛（进行中/未开始/已结束）
        repo = ContestRepo()
        status_filter = request.query_params.get("status")
        queryset = repo.get_queryset().order_by("-start_time")
        if status_filter:
            now = timezone.now()
            if status_filter == "running":
                queryset = queryset.filter(start_time__lte=now, end_time__gte=now)
            elif status_filter == "upcoming":
                queryset = queryset.filter(start_time__gt=now)
            elif status_filter == "ended":
                queryset = queryset.filter(end_time__lt=now)
        data = [serialize_contest(c) for c in queryset]
        return response.success({"items": data})

    def post(self, request: Request) -> Response:
        # 运行时切换为管理员权限
        self.permission_classes = [IsAdmin]  # type: ignore[assignment]
        # 序列化并创建比赛
        schema = ContestCreateSchema.from_dict(request.data, auto_validate=True)
        contest = CreateContestService().execute(schema)
        return response.created({"contest": serialize_contest(contest)}, message="比赛已创建")


class ContestDetailView(APIView):
    """比赛详情接口：返回比赛、挑战、公告、记分板及我的队伍。"""
    permission_classes = [AllowAny]
    context_service = ContestContextService()
    challenge_repo = ChallengeRepo()
    member_repo = TeamMemberRepo()
    scoreboard_service = ScoreboardService()

    def get(self, request: Request, slug: str) -> Response:
        # 获取比赛与基础信息
        contest = self.context_service.get_contest(slug)
        data = {
            "contest": serialize_contest(contest),
        }
        # 若已登录，附上用户所在队伍信息
        if request.user.is_authenticated:
            team = self.context_service.get_user_team(contest, request.user)
            if team:
                data["my_team"] = serialize_team(team)

        # 读取比赛下的有效题目列表
        challenges = self.challenge_repo.filter(contest=contest, is_active=True)
        data["challenges"] = [serialize_challenge(ch) for ch in challenges]
        # 公告：仅返回有效公告
        announcements = self.context_service.list_announcements(contest)
        data["announcements"] = [serialize_announcement(ann) for ann in announcements]
        # 计算记分板
        data["scoreboard"] = self.scoreboard_service.execute(contest)
        return response.success(data)


class ContestTeamsView(APIView):
    """比赛队伍列表 / 创建接口：需登录。"""
    permission_classes = [IsAuthenticated]
    context_service = ContestContextService()
    team_repo = TeamRepo()

    def get(self, request: Request, slug: str) -> Response:
        # 查询比赛并返回所有有效队伍
        contest = self.context_service.get_contest(slug)
        teams = self.team_repo.filter(contest=contest, is_active=True).select_related("captain")
        data = [serialize_team(team) for team in teams]
        return response.success({"contest": contest.slug, "teams": data})

    def post(self, request: Request, slug: str) -> Response:
        # 补充比赛标识后交由服务层创建队伍
        payload = dict(request.data)
        payload["contest_slug"] = slug
        schema = TeamCreateSchema.from_dict(payload, auto_validate=True)
        team = TeamCreateService().execute(request.user, schema)
        return response.created({"team": serialize_team(team)}, message="队伍已创建")


class ContestTeamJoinView(APIView):
    """加入队伍接口：需登录，通过邀请码加入。"""
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, slug: str) -> Response:
        # 补充比赛标识后交由服务层处理
        payload = dict(request.data)
        payload["contest_slug"] = slug
        schema = TeamJoinSchema.from_dict(payload, auto_validate=True)
        membership = TeamJoinService().execute(request.user, schema)
        return response.success(
            {"team": serialize_team(membership.team)},
            message="已加入队伍",
        )


class TeamLeaveView(APIView):
    """退出队伍接口：需登录，队长多人时需先转移/解散。"""
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, slug: str) -> Response:
        schema = TeamLeaveSchema.from_dict({"contest_slug": slug}, auto_validate=True)
        TeamLeaveService().execute(request.user, schema)
        return response.success(message="已退出队伍")


class TeamDisbandView(APIView):
    """解散队伍接口：需登录，队长或管理员可操作。"""
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, team_id: int) -> Response:
        schema = TeamDisbandSchema.from_dict({"team_id": team_id}, auto_validate=True)
        team = TeamDisbandService().execute(request.user, schema)
        return response.success({"team": serialize_team(team)}, message="队伍已解散")


class TeamInviteResetView(APIView):
    """
    重置队伍邀请码：
    - 队长或管理员操作。
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, team_id: int) -> Response:
        schema = TeamInviteResetSchema.from_dict({"team_id": team_id}, auto_validate=True)
        team = TeamInviteResetService().execute(request.user, schema)
        return response.success({"team": serialize_team(team)}, message="邀请码已重置")


class TeamTransferView(APIView):
    """
    队长移交：
    - 队长或管理员可操作，将队长角色转给指定队员。
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, team_id: int) -> Response:
        # 补充队伍 ID 后交由服务层移交
        payload = dict(request.data)
        payload["team_id"] = team_id
        schema = TeamTransferSchema.from_dict(payload, auto_validate=True)
        try:
            team = TeamTransferService().execute(request.user, schema)
            return response.success({"team": serialize_team(team)}, message="队长已移交")
        except Exception as exc:
            # 若业务错误导致移交失败，返回提示但不抛异常，便于前端展示。
            return response.success(message=f"队长移交失败：{exc}")


class ContestAnnouncementView(APIView):
    """
    比赛公告接口：
    - GET：任何人可查看比赛公告列表。
    - POST：管理员创建公告。
    """

    permission_classes = [AllowAny]
    context_service = ContestContextService()
    service = ContestAnnouncementService()

    def get(self, request: Request, slug: str) -> Response:
        # 获取比赛并返回有效公告列表
        contest = self.context_service.get_contest(slug)
        announcements = self.context_service.list_announcements(contest)
        return response.success({"items": [serialize_announcement(ann) for ann in announcements]})

    def post(self, request: Request, slug: str) -> Response:
        # 运行时切换为管理员权限并创建公告
        self.permission_classes = [IsAdmin]  # type: ignore[assignment]
        payload = dict(request.data)
        payload["contest_slug"] = slug
        schema = AnnouncementCreateSchema.from_dict(payload, auto_validate=True)
        ann = self.service.execute(schema)
        return response.created({"announcement": serialize_announcement(ann)}, message="公告已发布")
