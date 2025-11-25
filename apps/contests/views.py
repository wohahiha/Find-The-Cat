from __future__ import annotations

from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from drf_spectacular.types import OpenApiTypes

from apps.common import response
from apps.common.permissions import IsAuthenticated, IsAdmin, AllowAny
from apps.challenges.repo import ChallengeRepo
from apps.challenges.serializers import serialize_challenge
from apps.submissions.services import SubmissionService

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
    ContestExportService,
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

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    def get(self, request: Request) -> Response:
        # 公开接口：任何访客都可查看比赛列表，用于前台首页
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

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request) -> Response:
        # 运行时切换为管理员权限
        self.permission_classes = [IsAdmin]  # type: ignore[assignment]
        # 管理员创建比赛：先用 Schema 校验，再调用服务层持久化
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
    submit_service = SubmissionService()

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    def get(self, request: Request, contest_slug: str) -> Response:
        # contest_slug 来自路由占位符，用于定位比赛
        # 获取比赛对象，填充基础信息
        # 获取比赛与基础信息
        contest = self.context_service.get_contest(contest_slug)
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
        membership = None
        if request.user.is_authenticated:
            membership = self.member_repo.get_membership(contest=contest, user=request.user)
        data["challenges"] = [
            serialize_challenge(
                ch,
                # 查询当前用户在该题目下可见的分值（考虑动态降分/封榜）
                current_points=self.submit_service.visible_points_for_user(
                    request.user if request.user.is_authenticated else None,
                    contest,
                    ch,
                    membership=membership,
                ),
            )
            for ch in challenges
        ]
        # 公告：仅返回有效公告
        announcements = self.context_service.list_announcements(contest)
        data["announcements"] = [serialize_announcement(ann) for ann in announcements]
        # 计算记分板
        data["scoreboard"] = self.scoreboard_service.execute(contest)
        return response.success(data)


class ContestExportView(APIView):
    """比赛数据导出接口：仅管理员可用，返回 JSON 数据快照。"""

    permission_classes = [IsAdmin]
    export_service = ContestExportService()

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    def get(self, request: Request, contest_slug: str) -> Response:
        # contest_slug 路径参数：指定要导出的比赛
        # 后台导出：汇总比赛、题目、队伍、解题、提交与记分板快照
        payload = self.export_service.execute(contest_slug)
        return response.success(payload, message="导出成功")


class ContestTeamsView(APIView):
    """比赛队伍列表 / 创建接口：需登录。"""
    permission_classes = [IsAuthenticated]
    context_service = ContestContextService()
    team_repo = TeamRepo()

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    def get(self, request: Request, contest_slug: str) -> Response:
        # contest_slug 路径参数：限定需查询的比赛
        # 登录用户查看当前比赛所有有效队伍，便于选择加入
        # 查询比赛并返回所有有效队伍
        contest = self.context_service.get_contest(contest_slug)
        teams = self.team_repo.filter(contest=contest, is_active=True).select_related("captain")
        data = [serialize_team(team) for team in teams]
        return response.success({"contest": contest.slug, "teams": data})

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request, contest_slug: str) -> Response:
        # contest_slug 路径参数：锁定队伍所属比赛
        # 登录用户创建队伍：补充比赛标识后走服务层校验人数/权限
        # 补充比赛标识后交由服务层创建队伍
        payload = dict(request.data)
        payload["contest_slug"] = contest_slug
        schema = TeamCreateSchema.from_dict(payload, auto_validate=True)
        team = TeamCreateService().execute(request.user, schema)
        return response.created({"team": serialize_team(team)}, message="队伍已创建")


class ContestTeamJoinView(APIView):
    """加入队伍接口：需登录，通过邀请码加入。"""
    permission_classes = [IsAuthenticated]

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request, contest_slug: str) -> Response:
        # contest_slug 路径参数：确认邀请码所属比赛
        # 仅允许登录选手通过邀请码加入对应比赛队伍
        # 补充比赛标识后交由服务层处理
        payload = dict(request.data)
        payload["contest_slug"] = contest_slug
        schema = TeamJoinSchema.from_dict(payload, auto_validate=True)
        membership = TeamJoinService().execute(request.user, schema)
        return response.success(
            {"team": serialize_team(membership.team)},
            message="已加入队伍",
        )


class TeamLeaveView(APIView):
    """退出队伍接口：需登录，队长多人时需先转移/解散。"""
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request, contest_slug: str) -> Response:
        # contest_slug 路径参数：标识当前退出的比赛
        # 退出队伍：服务层校验队长限制与成员存在性
        schema = TeamLeaveSchema.from_dict({"contest_slug": contest_slug}, auto_validate=True)
        TeamLeaveService().execute(request.user, schema)
        return response.success(message="已退出队伍")


class TeamDisbandView(APIView):
    """解散队伍接口：需登录，队长或管理员可操作。"""
    permission_classes = [IsAuthenticated]

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request, team_id: int) -> Response:
        # team_id 路径参数：指定需解散的队伍
        # 由队长/管理员触发解散，服务层将成员标记失效
        schema = TeamDisbandSchema.from_dict({"team_id": team_id}, auto_validate=True)
        team = TeamDisbandService().execute(request.user, schema)
        return response.success({"team": serialize_team(team)}, message="队伍已解散")


class TeamInviteResetView(APIView):
    """
    重置队伍邀请码：
    - 队长或管理员操作。
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request, team_id: int) -> Response:
        # team_id 路径参数：定位需要更新邀请码的队伍
        # 触发重置：生成新邀请码并更新更新时间
        schema = TeamInviteResetSchema.from_dict({"team_id": team_id}, auto_validate=True)
        team = TeamInviteResetService().execute(request.user, schema)
        return response.success({"team": serialize_team(team)}, message="邀请码已重置")


class TeamTransferView(APIView):
    """
    队长移交：
    - 队长或管理员可操作，将队长角色转给指定队员。
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request, team_id: int) -> Response:
        # team_id 路径参数：队长移交的目标队伍
        # 将新队长用户 ID 传入服务层，完成角色切换
        # 补充队伍 ID 后交由服务层移交
        payload = dict(request.data)
        payload["team_id"] = team_id
        schema = TeamTransferSchema.from_dict(payload, auto_validate=True)
        team = TeamTransferService().execute(request.user, schema)
        return response.success({"team": serialize_team(team)}, message="队长已移交")


class ContestAnnouncementView(APIView):
    """
    比赛公告接口：
    - GET：任何人可查看比赛公告列表。
    - POST：管理员创建公告。
    """

    permission_classes = [AllowAny]
    context_service = ContestContextService()
    service = ContestAnnouncementService()

    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    def get(self, request: Request, contest_slug: str) -> Response:
        # contest_slug 路径参数：限定公告所属比赛
        # 公开公告列表：按创建时间倒序返回已启用公告
        # 获取比赛并返回有效公告列表
        contest = self.context_service.get_contest(contest_slug)
        announcements = self.context_service.list_announcements(contest)
        return response.success({"items": [serialize_announcement(ann) for ann in announcements]})

    @extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
    def post(self, request: Request, contest_slug: str) -> Response:
        # 运行时切换为管理员权限并创建公告
        self.permission_classes = [IsAdmin]  # type: ignore[assignment]
        # contest_slug 路径参数：指定公告关联的比赛
        # 将比赛标识加入 payload，使用 Schema 校验并调用服务落库
        payload = dict(request.data)
        payload["contest_slug"] = contest_slug
        schema = AnnouncementCreateSchema.from_dict(payload, auto_validate=True)
        ann = self.service.execute(schema)
        return response.created({"announcement": serialize_announcement(ann)}, message="公告已发布")
