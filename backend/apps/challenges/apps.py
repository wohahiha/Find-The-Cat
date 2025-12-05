from django.apps import AppConfig


class ChallengesConfig(AppConfig):
    """
    Challenges 应用配置：
    - 声明默认主键类型与应用路径，供 Django 注册模型/信号
    """

    default_auto_field = 'django.db.models.BigAutoField'  # 默认主键类型
    name = 'apps.challenges'  # 应用路径
    label = 'challenges'  # 应用标签
    verbose_name = "Challenges"  # 应用在后台显示的名称
