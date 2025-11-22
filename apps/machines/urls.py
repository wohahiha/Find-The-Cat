from __future__ import annotations

from django.urls import path

from .views import MachinePlaceholderView

app_name = "machines"

# 路由骨架：后续扩展靶机接口。
urlpatterns = [
    path("placeholder/", MachinePlaceholderView.as_view(), name="placeholder"),
]
