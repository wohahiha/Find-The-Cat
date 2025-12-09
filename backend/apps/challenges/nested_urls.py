"""
比赛内嵌套的题目路由：
- 挂载在 contests/<contest_slug>/challenges/ 下，由 contests.urls include
- 复用 Challenge 视图，提供列表/详情/提示/附件等接口
"""

from __future__ import annotations

from django.urls import path

from .views import (
    ChallengeListView,
    ChallengeDetailView,
    ChallengeHintListView,
    ChallengeHintUnlockView,
    ChallengeAttachmentDownloadView,
    ContestAttachmentUploadView,
)

app_name = "contest_challenges"

urlpatterns = [
    path("", ChallengeListView.as_view(), name="list"),
    path(
        "attachments/upload/",
        ContestAttachmentUploadView.as_view(),
        name="attachment-upload",
    ),
    path("<slug:challenge_slug>/", ChallengeDetailView.as_view(), name="detail"),
    path("<slug:challenge_slug>/hints/", ChallengeHintListView.as_view(), name="hint-list"),
    path(
        "<slug:challenge_slug>/hints/<int:hint_id>/unlock/",
        ChallengeHintUnlockView.as_view(),
        name="hint-unlock",
    ),
    path(
        "<slug:challenge_slug>/attachments/<int:attachment_id>/download/",
        ChallengeAttachmentDownloadView.as_view(),
        name="attachment-download",
    ),
]
