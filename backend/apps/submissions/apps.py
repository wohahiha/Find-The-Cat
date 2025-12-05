from django.apps import AppConfig


class SubmissionsConfig(AppConfig):
    """
    Submissions 应用配置：
    - 声明应用路径与默认主键类型，供 Django 注册模型与信号
    """

    default_auto_field = "django.db.models.BigAutoField"  # 默认主键类型
    name = "apps.submissions"  # 应用路径
    label = "submissions"  # 应用标签
    verbose_name = "Submissions"  # 应用在后台显示的名称
