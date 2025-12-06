from __future__ import annotations

from django.urls import path

from .views import (
    ChallengeListView,
    ChallengeDetailView,
    ChallengeHintListView,
    ChallengeHintUnlockView,
    ChallengeAttachmentDownloadView,
)

app_name = "challenges"

# 路由配置：
# - 嵌套在 contests/<contest_slug>/challenges/ 之下，由 contests.urls include
# - 提供题目列表/详情、提示列表/解锁、附件上传等接口；提交接口已统一到 submissions 模块
urlpatterns = [
    # 题目列表与创建
    path("", ChallengeListView.as_view(), name="list"),
    # 题目详情与更新
    path("<slug:challenge_slug>/", ChallengeDetailView.as_view(), name="detail"),
    # 提示列表与解锁
    path("<slug:challenge_slug>/hints/", ChallengeHintListView.as_view(), name="hint-list"),
    path("<slug:challenge_slug>/hints/<int:hint_id>/unlock/", ChallengeHintUnlockView.as_view(), name="hint-unlock"),
    # 附件下载（选手）
    path(
        "<slug:challenge_slug>/attachments/<int:attachment_id>/download/",
        ChallengeAttachmentDownloadView.as_view(),
        name="attachment-download",
    ),
]
