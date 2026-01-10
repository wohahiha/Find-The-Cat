from __future__ import annotations

from django.urls import path, include

from .views import (
    ContestListView,
    ContestDetailView,
    ContestRegisterView,
    AnnouncementListGlobalView,
    ContestTeamsView,
    ContestTeamJoinView,
    TeamLeaveView,
    TeamDisbandView,
    ContestAnnouncementView,
    ContestAnnouncementDetailView,
    TeamInviteResetView,
    TeamTransferView,
    ContestSubmissionView,
    ChallengeCategoryView,
    MyTeamsView,
)

# 路由配置：声明比赛、队伍、公告相关的 API 路径

app_name = "contests"

urlpatterns = [
    # 比赛列表 / 创建
    path("", ContestListView.as_view(), name="list"),
    # 全局公告列表
    path("announcements/", AnnouncementListGlobalView.as_view(), name="announcements-global"),
    # 报名参赛
    path("<slug:contest_slug>/register/", ContestRegisterView.as_view(), name="register"),
    # 比赛题目分类
    path("<slug:contest_slug>/categories/", ChallengeCategoryView.as_view(), name="categories"),
    # 队伍列表 / 创建
    path("<slug:contest_slug>/teams/", ContestTeamsView.as_view(), name="teams"),
    # 我的队伍（跨比赛）
    path("teams/mine/", MyTeamsView.as_view(), name="teams-mine"),
    # 加入队伍
    path("<slug:contest_slug>/teams/join/", ContestTeamJoinView.as_view(), name="team-join"),
    # 退出队伍
    path("<slug:contest_slug>/teams/leave/", TeamLeaveView.as_view(), name="team-leave"),
    # 解散队伍
    path("teams/<int:team_id>/disband/", TeamDisbandView.as_view(), name="team-disband"),
    # 重置邀请码
    path("teams/<int:team_id>/invite/reset/", TeamInviteResetView.as_view(), name="team-invite-reset"),
    # 队长移交
    path("teams/<int:team_id>/transfer/", TeamTransferView.as_view(), name="team-transfer"),
    # 比赛公告列表 / 创建
    path("<slug:contest_slug>/announcements/", ContestAnnouncementView.as_view(), name="announcements"),
    # 比赛公告详情
    path(
        "<slug:contest_slug>/announcements/<int:announcement_id>/",
        ContestAnnouncementDetailView.as_view(),
        name="announcement-detail",
    ),
    # 提交记录与判题（比赛作用域）
    path("<slug:contest_slug>/submissions/", ContestSubmissionView.as_view(), name="submissions"),
    # 嵌套挑战路由
    path(
        "<slug:contest_slug>/challenges/",
        include(("apps.challenges.nested_urls", "challenges"), namespace="contest-challenges"),
    ),
    # 比赛详情（含挑战、公告、记分板）
    path("<slug:contest_slug>/", ContestDetailView.as_view(), name="detail"),
]
