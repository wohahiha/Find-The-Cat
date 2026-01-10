"""
URL configuration for Config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from apps.common.health import HealthCheckView
from apps.system.services import ConfigService

# Admin 中文化：修改后台标题/页眉/站点名称，避免默认英文显示
def _get_brand():
    try:
        return ConfigService().get("SITE_BRAND", getattr(settings, "SITE_BRAND", "Find The Cat"))
    except Exception:
        return getattr(settings, "SITE_BRAND", "Find The Cat")

_brand = _get_brand()
admin.site.site_header = f"{_brand} 管理后台"
admin.site.site_title = _brand
admin.site.index_title = "管理控制台"

urlpatterns = [
    path('admin/', admin.site.urls),
    path('captcha/', include('captcha.urls')),
    path('health/', HealthCheckView.as_view()),
    path('api/accounts/', include('apps.accounts.urls')),
    path('api/contests/', include('apps.contests.urls')),
    path('api/machines/', include('apps.machines.urls')),
    path('api/problem-bank/', include('apps.problem_bank.urls')),
    path('api/system/', include('apps.system.urls')),
    path('api/notifications/', include('apps.notifications.urls')),
    path('api/auth/', include('apps.auth.urls')),
    # OpenAPI 文档：提供 schema JSON 及 UI，仅供内部/前端获取接口定义
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

# 开发环境提供媒体文件访问（用于后台预览上传的 Logo 等）
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
