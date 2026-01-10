from __future__ import annotations

from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from rest_framework import serializers

from apps.common import response
from apps.common.permissions import (
    IsAuthenticated,
    IsAdmin,
    AllowAny,
    IsAdminOrReadOnly,
    BizPermission,
    ensure_biz_permission,
)
from apps.challenges.repo import ChallengeRepo
from apps.challenges.serializers import serialize_challenge, serialize_category
from apps.submissions.services import SubmissionService, serialize_submission
from apps.common.pagination import StandardPagination
from django.db.models import Count, Q
from apps.submissions.repo import SubmissionRepo
from apps.submissions.schemas import SubmissionCreateSchema
from apps.common.schema_utils import (
    api_response_schema,
    list_response,
    contest_summary_serializer,
    challenge_summary_serializer,
    team_serializer,
    submission_payload_serializer,
    announcement_serializer,
    category_serializer,
    pagination_parameters,
    scoreboard_entry_serializer,
)
from .repo import ContestRepo, TeamRepo, TeamMemberRepo, ContestAnnouncementRepo
from .services import (
    ContestContextService,
    ContestRegisterService,
    ScoreboardService,
    ContestAnnouncementService,
    TeamInviteResetService,
    TeamTransferService,
    ContestCategoryUpdateService,
    serialize_announcement,
    ContestUpdateService,
    determine_contest_status,
)
from .schemas import (
    ContestCreateSchema,
    ContestUpdateSchema,
    TeamCreateSchema,
    TeamJoinSchema,
    TeamLeaveSchema,
    TeamDisbandSchema,
    AnnouncementCreateSchema,
    TeamInviteResetSchema,
    TeamTransferSchema,
    ContestCategoryUpdateSchema,
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
from apps.common.exceptions import BizError, TokenError, ValidationError, NotFoundError


_optional_team_serializer = team_serializer()
_optional_team_serializer.required = False
_optional_team_serializer.allow_null = True


# 视图层：暴露比赛、公告、队伍接口，仅做参数转换与调用服务层，不承载业务


class ContestListView(APIView):
    """比赛列表/创建接口：GET 公共访问，POST 仅管理员"""
    permission_classes = [AllowAny]
    pagination_class = StandardPagination
    context_service = ContestContextService()

    @extend_schema(
        summary="比赛列表",
        operation_id="contest_list",
        request=None,
        responses=list_response("ContestList", contest_summary_serializer(), paginated=True),
        parameters=[
            OpenApiParameter(
                name="status",
                location=OpenApiParameter.QUERY,
                description="比赛状态过滤",
                required=False,
                type=str,
                enum=["running", "upcoming", "ended"],
            ),
            *pagination_parameters(),
        ],
    )
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
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        data = [serialize_contest(c) for c in page]
        # 附加当前用户的报名/队伍标记
        if request.user.is_authenticated:
            participants = {
                p.contest_id: p
                for p in self.context_service.participant_repo.filter(contest__in=page, user=request.user)
            }
            memberships = {
                m.team.contest_id: m
                for m in self.context_service.member_repo.filter(team__contest__in=page, user=request.user, is_active=True)
            }
            slug_map = {c.slug: c for c in page}
            for item in data:
                contest_obj = slug_map.get(item.get("slug"))
                if not contest_obj:
                    continue
                cid = getattr(contest_obj, "id", None)
                participant = participants.get(cid)
                membership = memberships.get(cid)
                user_fields = self.context_service.build_user_contest_fields(
                    contest_obj,
                    participant=participant,
                    membership=membership,
                )
                item.update(user_fields)
        return paginator.get_paginated_response({"items": data})

    @extend_schema(
        summary="创建比赛",
        operation_id="contest_create",
        request=OpenApiTypes.OBJECT,
        responses=OpenApiTypes.OBJECT,
        exclude=True,  # 管理员专用，不暴露给前端文档
    )
    def post(self, request: Request) -> Response:
        ensure_biz_permission(request.user, "contests.manage_contest")
        schema = ContestCreateSchema.from_dict(request.data, auto_validate=True)
        contest = CreateContestService().execute(schema)
        categories = self.context_service.list_categories(contest)
        return response.created(
            {"contest": serialize_contest(contest, categories=categories)},
            message="比赛已创建",
        )


class ContestRegisterView(APIView):
    """比赛报名接口：选手点击报名后写入参赛记录"""

    permission_classes = [IsAuthenticated, BizPermission]
    biz_permission = "contests.view_contest"
    context_service = ContestContextService()
    register_service = ContestRegisterService()

    @extend_schema(
        summary="报名参赛",
        operation_id="contest_register",
        request=None,
        responses=api_response_schema(
            "ContestRegister",
            {"contest": contest_summary_serializer(), "status": serializers.CharField(help_text="报名状态")},
        ),
        tags=["contests"],
    )
    def post(self, request: Request, contest_slug: str) -> Response:
        """报名后生成/更新参赛记录，未开赛为已报名，开赛后为进行中"""
        contest = self.context_service.get_contest(contest_slug)
        participant = self.register_service.execute(request.user, contest_slug)
        categories = self.context_service.list_categories(contest)
        return response.success(
            {
                "contest": serialize_contest(contest, categories=categories),
                "status": participant.status,
            },
            message="报名成功",
        )


class ContestDetailView(APIView):
    """比赛详情接口：返回比赛、挑战、公告、记分板及我的队伍"""
    permission_classes = [AllowAny]
    biz_permission = "contests.view_contest"
    context_service = ContestContextService()
    challenge_repo = ChallengeRepo()
    member_repo = TeamMemberRepo()
    scoreboard_service = ScoreboardService()
    submit_service = SubmissionService()
    update_service = ContestUpdateService()

    @extend_schema(
        summary="比赛详情",
        operation_id="contest_detail",
        request=None,
        responses=api_response_schema(
            "ContestDetail",
            {
                "contest": contest_summary_serializer(),
                "my_team": _optional_team_serializer,
                "challenges": challenge_summary_serializer(many=True),
                "announcements": announcement_serializer(many=True),
                "scoreboard": scoreboard_entry_serializer(many=True),
                "my_scoreboard": scoreboard_entry_serializer(required=False, allow_null=True),
            },
        ),
    )
    def get(self, request: Request, contest_slug: str) -> Response:
        # contest_slug 来自路由占位符，用于定位比赛
        # 获取比赛对象，填充基础信息
        # 获取比赛与基础信息
        contest = self.context_service.get_contest(contest_slug)
        self.context_service.ensure_contest_visible(contest, request.user if request.user.is_authenticated else None)
        categories = self.context_service.list_categories(contest)
        participant = None
        membership = None
        if request.user.is_authenticated:
            participant = self.context_service.mark_participation(contest, request.user, allow_create=False)
            membership = self.member_repo.get_membership(contest=contest, user=request.user)
        data = {
            "contest": serialize_contest(contest, categories=categories),
        }
        # 若已登录，附上用户所在队伍信息
        if membership and getattr(membership, "team", None):
            data["my_team"] = serialize_team(membership.team)

        # 读取比赛下的有效题目列表
        challenges = self.challenge_repo.list_active_with_related(contest=contest)
        if request.user.is_authenticated:
            user_fields = self.context_service.build_user_contest_fields(
                contest,
                participant=participant,
                membership=membership,
            )
            data["contest"].update(user_fields)
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
                request=request,
            )
            for ch in challenges
        ]
        # 公告：仅返回有效公告
        announcements = self.context_service.list_announcements(contest)
        data["announcements"] = [serialize_announcement(ann) for ann in announcements]
        # 计算记分板
        raw_scoreboard = self.scoreboard_service.execute(contest)
        scoreboard_payload: list[dict] = []
        my_row = None
        current_team_id = getattr(membership, "team_id", None) if membership else None
        current_user_id = getattr(request.user, "id", None) if request.user.is_authenticated else None
        for entry in raw_scoreboard:
            team_info = entry.get("team") or {}
            user_info = entry.get("user") or {}
            team_id = team_info.get("id")
            user_id = user_info.get("id")
            name = team_info.get("name") or user_info.get("username") or ""
            is_me = False
            if contest.is_team_based and current_team_id and team_id == current_team_id:
                is_me = True
            if not contest.is_team_based and current_user_id and user_id == current_user_id:
                is_me = True
            payload = {
                **entry,
                "team_id": team_id,
                "user_id": user_id,
                "name": name,
                "is_me": is_me,
            }
            scoreboard_payload.append(payload)
            if is_me and my_row is None:
                my_row = payload
        data["scoreboard"] = scoreboard_payload
        data["my_scoreboard"] = my_row
        return response.success(data)

    @extend_schema(
        summary="更新比赛信息",
        operation_id="contest_update",
        request=OpenApiTypes.OBJECT,
        responses=OpenApiTypes.OBJECT,
        tags=["contests"],
        exclude=True,  # 管理员专用，不在前端文档展示
    )
    def patch(self, request: Request, contest_slug: str) -> Response:
        """管理员更新比赛基础信息：时间窗口、可见性等"""
        ensure_biz_permission(request.user, "contests.manage_contest")
        payload = dict(request.data or {})
        payload["contest_slug"] = contest_slug
        schema = ContestUpdateSchema.from_dict(payload, auto_validate=True)
        contest = self.update_service.execute(schema)
        categories = self.context_service.list_categories(contest)
        return response.success(
            {"contest": serialize_contest(contest, categories=categories)},
            message="比赛信息已更新",
        )


class ContestExportView(APIView):
    """比赛数据导出接口：仅管理员可用，返回 JSON 数据快照"""

    permission_classes = [IsAdmin, BizPermission]
    biz_permission = "contests.export_contest_data"
    export_service = ContestExportService()

    @extend_schema(
        request=None,
        responses=OpenApiTypes.OBJECT,
        description="管理员导出比赛快照（比赛/题目/队伍/解题/提交/记分板），需 contests.export_contest_data 权限",
    )
    def get(self, request: Request, contest_slug: str) -> Response:
        # contest_slug 路径参数：指定要导出的比赛
        # 后台导出：汇总比赛、题目、队伍、解题、提交与记分板快照（管理员专用）
        _ = request  # 未使用参数
        payload = self.export_service.execute(contest_slug)
        return response.success(payload, message="导出成功")


class ContestSubmissionView(APIView):
    """
    比赛提交接口：
    - POST：比赛作用域内提交 Flag
    - GET：选手查看个人/所在队伍的提交记录
    """

    permission_classes = [IsAuthenticated, BizPermission]
    biz_permission_map = {
        "post": "challenges.submit_contest_flag",
        "get": "submissions.view_submission",
    }
    pagination_class = StandardPagination
    context_service = ContestContextService()
    service = SubmissionService()
    repo = SubmissionRepo()
    member_repo = TeamMemberRepo()

    @extend_schema(
        responses=api_response_schema(
            "ContestSubmission",
            {
                "submission": submission_payload_serializer(),
                "challenge": challenge_summary_serializer(),
                "awarded_points": serializers.IntegerField(help_text="总得分"),
                "bonus_points": serializers.IntegerField(help_text="额外加分"),
                "solved_at": serializers.DateTimeField(required=False, allow_null=True),
            },
        ),
        summary="比赛内提交 Flag",
        tags=["submissions"],
        request=inline_serializer(
            name="ContestSubmissionRequest",
            fields={
                "challenge_slug": serializers.CharField(help_text="题目标识"),
                "flag": serializers.CharField(help_text="提交的 Flag"),
            },
        ),
    )
    def post(self, request: Request, contest_slug: str) -> Response:
        """比赛作用域内提交 Flag"""
        payload = dict(request.data)
        payload["contest_slug"] = contest_slug
        contest = self.context_service.get_contest(contest_slug)
        self.context_service.ensure_contest_visible(contest, request.user)
        schema = SubmissionCreateSchema.from_dict(payload, auto_validate=True)
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

    @extend_schema(
        request=None,
        responses=list_response(
            "ContestSubmissionList",
            submission_payload_serializer(),
            paginated=True,
        ),
        summary="我的提交记录",
        tags=["submissions"],
        parameters=[
            OpenApiParameter(
                name="scope",
                location=OpenApiParameter.QUERY,
                description="提交记录范围，组队赛可选 team",
                required=False,
                type=str,
                enum=["personal", "team"],
            ),
            *pagination_parameters(),
        ],
    )
    def get(self, request: Request, contest_slug: str) -> Response:
        """
        查看当前用户的提交记录：
        - scope=personal（默认）：仅本人提交
        - scope=team（组队赛）：查看所在队伍的提交
        """
        contest = ContestRepo().get_by_slug(contest_slug)
        self.context_service.ensure_contest_visible(contest, request.user)
        scope = request.query_params.get("scope", "personal")
        membership = self.member_repo.get_membership(contest=contest, user=request.user)
        queryset = self.repo.filter(contest=contest).select_related("challenge", "user", "team")
        if contest.is_team_based and scope == "team" and membership and getattr(membership, "team_id", None):
            queryset = queryset.filter(team_id=membership.team_id)  # type: ignore[attr-defined]
        else:
            queryset = queryset.filter(user=request.user)
        queryset = queryset.order_by("-created_at")
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        items = [serialize_submission(sub) for sub in page]
        return paginator.get_paginated_response({"items": items})


class ContestTeamsView(APIView):
    """比赛队伍列表 / 创建接口：需登录"""
    permission_classes = [IsAuthenticated, BizPermission]
    biz_permission_map = {
        "get": "teams.view_team",
        "post": "teams.manage_team",
    }
    pagination_class = StandardPagination
    context_service = ContestContextService()
    team_repo = TeamRepo()

    @extend_schema(
        summary="比赛队伍列表",
        request=None,
        responses=list_response(
            "ContestTeamList",
            team_serializer(),
            extra_fields={"contest": serializers.CharField(help_text="比赛标识")},
            paginated=True,
        ),
        tags=["teams"],
        parameters=pagination_parameters(),
    )
    def get(self, request: Request, contest_slug: str) -> Response:
        # contest_slug 路径参数：限定需查询的比赛
        # 登录用户查看当前比赛所有有效队伍，便于选择加入
        # 查询比赛并返回所有有效队伍
        contest = self.context_service.get_contest(contest_slug)
        teams = (
            self.team_repo.filter_with_related(contest=contest, is_active=True)
            .annotate(active_member_count=Count("members", filter=Q(members__is_active=True)))
            .order_by("name", "id")
        )
        paginator = StandardPagination()
        page_items = paginator.paginate_queryset(teams, request)
        data = [serialize_team(team) for team in page_items]
        return paginator.get_paginated_response({"contest": contest.slug, "items": data})

    @extend_schema(
        summary="创建队伍",
        request=inline_serializer(
            name="TeamCreateRequest",
            fields={
                "name": serializers.CharField(help_text="队伍名称"),
                "description": serializers.CharField(required=False, allow_blank=True, help_text="队伍简介"),
            },
        ),
        responses=api_response_schema("TeamCreate", {"team": team_serializer()}),
        tags=["teams"],
    )
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
    """加入队伍接口：需登录，通过邀请码加入"""
    permission_classes = [IsAuthenticated, BizPermission]
    biz_permission = "teams.join_team"

    @extend_schema(
        summary="加入队伍",
        request=inline_serializer(
            name="TeamJoinRequest",
            fields={
                "invite_token": serializers.CharField(help_text="队伍邀请码"),
            },
        ),
        responses=api_response_schema("TeamJoin", {"team": team_serializer()}),
        tags=["teams"],
    )
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
    """退出队伍接口：需登录，队长多人时需先转移/解散"""
    permission_classes = [IsAuthenticated, BizPermission]
    biz_permission = "teams.leave_team"

    @extend_schema(
        summary="退出队伍",
        request=None,
        responses=api_response_schema("TeamLeave", {}),
        tags=["teams"],
    )
    def post(self, request: Request, contest_slug: str) -> Response:
        # contest_slug 路径参数：标识当前退出的比赛
        # 退出队伍：服务层校验队长限制与成员存在性
        schema = TeamLeaveSchema.from_dict({"contest_slug": contest_slug}, auto_validate=True)
        TeamLeaveService().execute(request.user, schema)
        return response.success(message="已退出队伍")


class TeamDisbandView(APIView):
    """解散队伍接口：需登录，队长或管理员可操作"""
    permission_classes = [IsAuthenticated, BizPermission]
    biz_permission = "teams.manage_team"

    @extend_schema(
        summary="解散队伍",
        request=None,
        responses=api_response_schema("TeamDisband", {"team": team_serializer()}),
        tags=["teams"],
    )
    def post(self, request: Request, team_id: int) -> Response:
        # team_id 路径参数：指定需解散的队伍
        # 由队长/管理员触发解散，服务层将成员标记失效
        schema = TeamDisbandSchema.from_dict({"team_id": team_id}, auto_validate=True)
        team = TeamDisbandService().execute(request.user, schema)
        return response.success({"team": serialize_team(team)}, message="队伍已解散")


class TeamInviteResetView(APIView):
    """
    重置队伍邀请码：
    - 队长或管理员操作
    """

    permission_classes = [IsAuthenticated, BizPermission]
    biz_permission = "teams.manage_team"

    @extend_schema(
        summary="重置队伍邀请码",
        request=None,
        responses=api_response_schema("TeamInviteReset", {"team": team_serializer()}),
        tags=["teams"],
    )
    def post(self, request: Request, team_id: int) -> Response:
        # team_id 路径参数：定位需要更新邀请码的队伍
        # 触发重置：生成新邀请码并更新更新时间
        schema = TeamInviteResetSchema.from_dict({"team_id": team_id}, auto_validate=True)
        team = TeamInviteResetService().execute(request.user, schema)
        return response.success({"team": serialize_team(team)}, message="邀请码已重置")


class TeamTransferView(APIView):
    """
    队长移交：
    - 队长或管理员可操作，将队长角色转给指定队员
    """

    permission_classes = [IsAuthenticated, BizPermission]
    biz_permission = "teams.manage_team"

    @extend_schema(
        summary="队长移交",
        request=inline_serializer(
            name="TeamTransferRequest",
            fields={
                "new_captain_id": serializers.IntegerField(help_text="新队长用户 ID"),
            },
        ),
        responses=api_response_schema("TeamTransfer", {"team": team_serializer()}),
        tags=["teams"],
    )
    def post(self, request: Request, team_id: int) -> Response:
        # team_id 路径参数：队长移交的目标队伍
        # 将新队长用户 ID 传入服务层，完成角色切换
        # 补充队伍 ID 后交由服务层移交
        payload = dict(request.data)
        payload["team_id"] = team_id
        schema = TeamTransferSchema.from_dict(payload, auto_validate=True)
        team = TeamTransferService().execute(request.user, schema)
        return response.success({"team": serialize_team(team)}, message="队长已移交")


class ChallengeCategoryView(APIView):
    """
    比赛题目分类管理：
    - GET：公开查询比赛下的题目分类列表
    - PATCH：管理员更新题目分类
    """

    permission_classes = [AllowAny]
    context_service = ContestContextService()
    service = ContestCategoryUpdateService()

    @extend_schema(
        summary="比赛题目分类列表",
        request=None,
        responses=list_response("ContestCategoryList", category_serializer()),
    )
    def get(self, request: Request, contest_slug: str) -> Response:
        _ = request
        contest = self.context_service.get_contest(contest_slug)
        categories = self.context_service.list_categories(contest)
        return response.success({"items": [serialize_category(cat) for cat in categories]})

    @extend_schema(
        summary="更新比赛题目分类",
        request=inline_serializer(
            name="ContestCategoryUpdate",
            fields={
                "categories": serializers.ListField(
                    child=serializers.CharField(),
                    help_text="分类名称列表",
                )
            },
        ),
        responses=list_response("ContestCategoryUpdate", category_serializer()),
        exclude=True,  # 管理员专用
    )
    def patch(self, request: Request, contest_slug: str) -> Response:
        ensure_biz_permission(request.user, "contests.manage_contest")
        payload = dict(request.data or {})
        payload["contest_slug"] = contest_slug
        schema = ContestCategoryUpdateSchema.from_dict(payload, auto_validate=True)
        categories = self.service.execute(schema)
        return response.success(
            {"items": [serialize_category(cat) for cat in categories]},
            message="题目分类已更新",
        )

    @extend_schema(
        summary="更新比赛题目分类（兼容 PUT）",
        request=OpenApiTypes.OBJECT,
        responses=OpenApiTypes.OBJECT,
        tags=["contests"],
        operation_id="contest_category_update_put",
        exclude=True,  # 管理员专用
    )
    def put(self, request: Request, contest_slug: str) -> Response:
        """兼容旧前端的 PUT 方法，复用 PATCH 逻辑"""
        return self.patch(request, contest_slug)


class MyTeamsView(APIView):
    """
    我的战队列表（跨比赛）：返回我参与过或正在参与的队伍
    """

    permission_classes = [IsAuthenticated]
    context_service = ContestContextService()

    @extend_schema(
        summary="我的战队列表",
        request=None,
        responses=api_response_schema(
            "MyTeams",
            {
                "items": serializers.ListSerializer(
                    child=inline_serializer(
                        name="MyTeamItem",
                        fields={
                            "id": serializers.IntegerField(required=False, allow_null=True),
                            "name": serializers.CharField(required=False, allow_null=True),
                            "invite_token": serializers.CharField(required=False, allow_null=True),
                            "role": serializers.CharField(required=False, allow_null=True),
                            "is_active": serializers.BooleanField(required=False),
                            "joined_at": serializers.DateTimeField(required=False, allow_null=True),
                            "status": serializers.CharField(required=False, allow_null=True),
                            "contest": inline_serializer(
                                name="MyTeamContest",
                                fields={
                                    "id": serializers.IntegerField(required=False, allow_null=True),
                                    "slug": serializers.CharField(required=False, allow_null=True),
                                    "name": serializers.CharField(required=False, allow_null=True),
                                    "start_time": serializers.DateTimeField(required=False, allow_null=True),
                                    "end_time": serializers.DateTimeField(required=False, allow_null=True),
                                },
                            ),
                        },
                    )
                )
            },
        ),
        tags=["teams"],
    )
    def get(self, request: Request) -> Response:
        user = request.user
        member_repo = self.context_service.member_repo
        memberships = (
            member_repo.filter(user=user)
            .select_related("team", "team__contest")
            .order_by("-joined_at")
        )

        items = []
        for m in memberships:
            team = getattr(m, "team", None)
            contest = getattr(team, "contest", None) if team else None
            items.append(
                {
                    "id": getattr(team, "id", None),
                    "name": getattr(team, "name", None),
                    "invite_token": getattr(team, "invite_token", None),
                    "role": getattr(m, "role", None),
                    "is_active": getattr(m, "is_active", None),
                    "joined_at": getattr(m, "joined_at", None),
                    "contest": serialize_contest(contest) if contest else None,
                    "status": determine_contest_status(contest) if contest else None,
                }
            )
        return response.success({"items": items})


class ContestAnnouncementView(APIView):
    """
    比赛公告接口：
    - GET：任何人可查看比赛公告列表
    - POST：管理员创建公告
    """

    permission_classes = [AllowAny]
    pagination_class = StandardPagination
    context_service = ContestContextService()
    service = ContestAnnouncementService()
    announcement_repo = ContestAnnouncementRepo()

    @extend_schema(
        summary="比赛公告列表",
        operation_id="contests_announcements_list",
        request=None,
        responses=list_response("AnnouncementList", announcement_serializer(), paginated=True),
        parameters=pagination_parameters(),
    )
    def get(self, request: Request, contest_slug: str) -> Response:
        # contest_slug 路径参数：限定公告所属比赛
        # 公开公告列表：按创建时间倒序返回已启用公告
        # 获取比赛并返回有效公告列表
        contest = self.context_service.get_contest(contest_slug)
        announcements = self.context_service.list_announcements(contest)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(announcements, request)
        items = [serialize_announcement(ann) for ann in page]
        return paginator.get_paginated_response({"items": items})

    @extend_schema(
        summary="创建比赛公告",
        operation_id="contests_announcements_create",
        request=inline_serializer(
            name="AnnouncementCreate",
            fields={
                "title": serializers.CharField(),
                "summary": serializers.CharField(help_text="公告摘要"),
                "content": serializers.CharField(),
                "is_active": serializers.BooleanField(required=False),
            },
        ),
        responses=api_response_schema("AnnouncementCreate", {"announcement": announcement_serializer()}),
        exclude=True,
    )
    def post(self, request: Request, contest_slug: str) -> Response:
        _ = request
        ensure_biz_permission(request.user, "contests.manage_announcement")
        # contest_slug 路径参数：指定公告关联的比赛
        # 将比赛标识加入 payload，使用 Schema 校验并调用服务落库
        payload = dict(request.data)
        payload["contest_slug"] = contest_slug
        schema = AnnouncementCreateSchema.from_dict(payload, auto_validate=True)
        ann = self.service.execute(schema)
        return response.created({"announcement": serialize_announcement(ann)}, message="公告已发布")


class ContestAnnouncementDetailView(APIView):
    """
    比赛公告详情：需登录查看指定公告
    """

    permission_classes = [IsAuthenticated, BizPermission]
    biz_permission = "contests.view_contest"
    context_service = ContestContextService()
    announcement_repo = ContestAnnouncementRepo()

    @extend_schema(
        summary="比赛公告详情",
        operation_id="contests_announcements_detail",
        request=None,
        responses=api_response_schema("AnnouncementDetail", {"announcement": announcement_serializer()}),
    )
    def get(self, request: Request, contest_slug: str, announcement_id: int) -> Response:
        _ = self
        contest = self.context_service.get_contest(contest_slug)
        self.context_service.ensure_contest_visible(contest, request.user)
        ann = self.announcement_repo.get_by_id(announcement_id)
        if ann.contest_id != contest.id:  # type: ignore[attr-defined]
            raise NotFoundError(message="公告不存在")
        return response.success({"announcement": serialize_announcement(ann)})


class AnnouncementListGlobalView(APIView):
    """
    全局公告列表：可选按比赛过滤，公开访问
    """

    permission_classes = [AllowAny]
    pagination_class = StandardPagination
    announcement_repo = ContestAnnouncementRepo()

    @extend_schema(
        summary="全局公告列表",
        operation_id="announcement_list_global",
        request=None,
        responses=list_response("AnnouncementListGlobal", announcement_serializer(), paginated=True),
        parameters=[
            OpenApiParameter(
                name="contest",
                location=OpenApiParameter.QUERY,
                description="可选比赛标识（slug），为空则返回所有公告",
                required=False,
                type=str,
            ),
            *pagination_parameters(),
        ],
    )
    def get(self, request: Request) -> Response:
        slug = request.query_params.get("contest")
        queryset = self.announcement_repo.get_queryset().filter(is_active=True).select_related("contest").order_by("-created_at")
        if slug:
            queryset = queryset.filter(contest__slug=slug)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(queryset, request)
        items = [serialize_announcement(ann) for ann in page]
        return paginator.get_paginated_response({"items": items})
