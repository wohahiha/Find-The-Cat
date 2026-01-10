"""
ASGI config for Config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Config.settings')

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

# 先初始化 Django，确保 AppRegistry 就绪
django_application = get_asgi_application()

# WebSocket 路由与 JWT 鉴权中间件（延后加载以避免 AppRegistryNotReady）
from Config.routing import websocket_urlpatterns  # noqa: E402
from apps.common.ws_auth import JWTAuthMiddleware  # noqa: E402

# HTTP 仍由 Django 处理；WebSocket 通过 JWTAuthMiddleware + AuthMiddlewareStack 解析用户
application = ProtocolTypeRouter({
    "http": django_application,
    "websocket": JWTAuthMiddleware(
        AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        )
    ),
})
