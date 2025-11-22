from __future__ import annotations

from django.urls import path

from .views import ChallengeListView, ChallengeDetailView, ChallengeSubmitView

app_name = "challenges"

# 路由：题目列表/详情/提交接口。
urlpatterns = [
    # 题目列表与创建
    path("", ChallengeListView.as_view(), name="list"),
    # 题目详情与更新
    path("<slug:challenge_slug>/", ChallengeDetailView.as_view(), name="detail"),
    # 提交 Flag
    path("<slug:challenge_slug>/submit/", ChallengeSubmitView.as_view(), name="submit"),
]
