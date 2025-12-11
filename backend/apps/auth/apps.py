# -*- coding: utf-8 -*-
from django.apps import AppConfig


class AuthConfig(AppConfig):
    """
    认证与权限（轻量级 RBAC）应用配置
    - label 设置为 ftc_auth 以避免与 django.contrib.auth 冲突
    - 后续将承载 OAuth2、角色/权限管理等
    """

    name = "apps.auth"
    label = "ftc_auth"
    verbose_name = "Authentication And Authorization"

    def ready(self):
        """
        启动钩子：同步权限字典与默认角色
        - 避开 migrate/makemigrations/collectstatic 阶段，防止 DB 未就绪
        """
        import sys
        try:
            cmd = sys.argv[1].lower() if len(sys.argv) > 1 else ""
            if cmd in {"migrate", "makemigrations", "collectstatic"}:
                return
        except Exception:
            return
        try:
            from apps.auth.services import RBACService
            RBACService.sync_permissions_and_defaults()
        except Exception:
            # 同步失败不阻断启动，交由管理员手动触发
            return
