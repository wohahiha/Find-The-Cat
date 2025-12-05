# -*- coding: utf-8 -*-
"""
全局 WebSocket 路由配置

- 提供基础通知通道与比赛事件通道
- 鉴权与权限在 Consumer 内校验
"""

from django.urls import path

from apps.common.consumers import NotifyConsumer, ContestEventConsumer

websocket_urlpatterns = [
    path("ws/notify/", NotifyConsumer.as_asgi(), name="ws-notify"),
    path("ws/contests/<slug:contest_slug>/", ContestEventConsumer.as_asgi(), name="ws-contest-events"),
]
