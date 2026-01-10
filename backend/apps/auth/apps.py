# -*- coding: utf-8 -*-
from django.apps import AppConfig
from django.db.models.signals import post_migrate


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
        启动钩子：注册 post_migrate 信号，避免在 App 初始化阶段直接访问数据库
        """
        from apps.common.infra.logger import get_logger

        logger = get_logger(__name__)

        def sync_rbac(**kwargs):
            _ = kwargs  # 未使用
            try:
                from apps.auth.services import RBACService

                RBACService.sync_permissions_and_defaults()
                logger.info("RBAC 权限/默认角色已同步")
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"RBAC 同步跳过（可能数据库未就绪或命令上下文不适用）：{exc}")

        post_migrate.connect(sync_rbac, sender=self, weak=False)
