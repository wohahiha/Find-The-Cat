from django.apps import AppConfig


class ContestsConfig(AppConfig):
    """
    Contests 应用配置：
    - 声明应用名称与默认主键类型
    - 供 Django 自动发现模型与信号
    """

    default_auto_field = 'django.db.models.BigAutoField'  # 默认主键类型
    name = 'apps.contests'  # 应用路径
    label = 'contests'  # 应用标签
    verbose_name = "Contests"  # 应用在后台显示的名称
