from __future__ import annotations

from django.urls import path

from .views import (
    ChallengeListView,
    ChallengeDetailView,
    ChallengeHintListView,
    ChallengeHintUnlockView,
    AttachmentUploadView,
)

app_name = "challenges"

# 路由：题目列表/详情/提交接口。
urlpatterns = [
    # 题目列表与创建
    path("", ChallengeListView.as_view(), name="list"),
    # 题目详情与更新
    path("<slug:challenge_slug>/", ChallengeDetailView.as_view(), name="detail"),
    # 提示列表与解锁
    path("<slug:challenge_slug>/hints/", ChallengeHintListView.as_view(), name="hint-list"),
    path("<slug:challenge_slug>/hints/<int:hint_id>/unlock/", ChallengeHintUnlockView.as_view(), name="hint-unlock"),
    # 附件上传（管理员）
    path("attachments/upload/", AttachmentUploadView.as_view(), name="attachment-upload"),
]
