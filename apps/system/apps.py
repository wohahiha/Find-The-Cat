from django.apps import AppConfig


class ConfigsConfig(AppConfig):
    """系统配置模块 AppConfig，用于注册后台动态配置"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.system"

    # 继续使用原 app label，保证迁移与表名兼容
    label = "configs"
    verbose_name = "SYSTEM"
