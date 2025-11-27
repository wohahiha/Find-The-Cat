from __future__ import annotations

from django.urls import path

from .views import SubmissionCreateView

app_name = "submissions"

# 路由：提交 Flag 接口
urlpatterns = [
    path("", SubmissionCreateView.as_view(), name="create"),
]
