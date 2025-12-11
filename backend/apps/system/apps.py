from django.apps import AppConfig
from django.db.models.signals import post_migrate


class ConfigsConfig(AppConfig):
    """
    系统配置模块 AppConfig

    职责：
    1. 注册后台动态配置（SystemConfig 模型）
    2. Django 启动时自动初始化"基础配置"（将 settings.py 默认值填入数据库）

    注意：
    - 首次启动（migrate 后）会自动创建 33 个配置项，值来自 settings.py
    - 后续启动会同步配置元数据（类型、描述、敏感性等），但不覆盖已设置的值
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.system"

    # 继续使用原 app label，保证迁移与表名兼容
    label = "configs"
    verbose_name = "System"

    def ready(self):
        """
        Django 启动完成后的钩子：初始化日志系统，并在 migrations 完成后同步配置

        逻辑拆分：
        1. ready() 内只做“无数据库访问”的初始化（配置日志）
        2. 数据库相关的 ensure_supported_configs 放到 post_migrate 信号中执行
        """
        from apps.common.infra.logger import (
            configure_logging,
            get_logger,
            get_log_path_from_settings,
        )

        # 初始化日志系统（使用 settings 默认值，避免在 ready 阶段访问数据库）
        configure_logging(
            force=True,
            log_file_path=get_log_path_from_settings(),
        )
        logger = get_logger(__name__)

        # 启动时尝试读取后台安全配置并覆盖 settings（失败不阻断启动）
        try:
            import sys
            from .services import apply_security_settings_from_config

            # 避免在迁移/建模阶段访问数据库：检测当前命令，遇到 migrate/makemigrations/collectstatic 时跳过
            command = sys.argv[1].lower() if len(sys.argv) > 1 else ""
            if command not in {"migrate", "makemigrations", "collectstatic"}:
                apply_security_settings_from_config()
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"应用安全配置覆盖失败，继续使用默认值: {exc}")

        def sync_system_configs(**kwargs):
            """
            post_migrate 信号回调：确保 SystemConfig 表中的配置项齐全
            """
            _ = kwargs  # 未使用参数
            try:
                from .services import ConfigService

                config_service = ConfigService()
                config_service.ensure_supported_configs()
                # 确保日志系统重新读取数据库配置
                configure_logging(force=True)
                logger.info("系统配置自动初始化完成：已同步 SUPPORTED_CONFIGS 到数据库")
            except Exception as exc:
                logger.warning(f"系统配置自动初始化跳过（可能是首次 migrate 或数据库不可用）: {exc}")

        # 仅在 migrations 执行完毕后再访问数据库，避免 AppConfig.ready() 访问数据库的警告
        post_migrate.connect(sync_system_configs, sender=self, weak=False)
