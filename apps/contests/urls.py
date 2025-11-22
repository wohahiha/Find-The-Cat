from __future__ import annotations

from django.urls import path, include

from .views import (
    ContestListView,
    ContestDetailView,
    ContestTeamsView,
    ContestTeamJoinView,
    TeamLeaveView,
    TeamDisbandView,
    ContestAnnouncementView,
    TeamInviteResetView,
    TeamTransferView,
)

# 路由配置：声明比赛、队伍、公告相关的 API 路径。

app_name = "contests"

urlpatterns = [
    # 比赛列表 / 创建
    path("", ContestListView.as_view(), name="list"),
    # 比赛详情（含挑战、公告、记分板）
    path("<slug:slug>/", ContestDetailView.as_view(), name="detail"),
    # 队伍列表 / 创建
    path("<slug:slug>/teams/", ContestTeamsView.as_view(), name="teams"),
    # 加入队伍
    path("<slug:slug>/teams/join/", ContestTeamJoinView.as_view(), name="team-join"),
    # 退出队伍
    path("<slug:slug>/teams/leave/", TeamLeaveView.as_view(), name="team-leave"),
    # 解散队伍
    path("teams/<int:team_id>/disband/", TeamDisbandView.as_view(), name="team-disband"),
    # 重置邀请码
    path("teams/<int:team_id>/invite/reset/", TeamInviteResetView.as_view(), name="team-invite-reset"),
    # 队长移交
    path("teams/<int:team_id>/transfer/", TeamTransferView.as_view(), name="team-transfer"),
    # 比赛公告列表 / 创建
    path("<slug:slug>/announcements/", ContestAnnouncementView.as_view(), name="announcements"),
    # 嵌套挑战路由
    path(
        "<slug:contest_slug>/challenges/",
        include(("apps.challenges.urls", "challenges"), namespace="contest-challenges"),
    ),
]
