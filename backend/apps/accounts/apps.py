from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """
    账户模块应用配置：
    - 注册 accounts 应用的基本信息（名称、标签、默认主键类型）
    - 在 Django 启动时加载 signals，绑定用户/邮箱等领域事件
    """

    # 默认主键类型：使用 BigAutoField，避免主键溢出
    default_auto_field = "django.db.models.BigAutoField"
    # 应用全路径：与 Django INSTALLED_APPS 保持一致
    name = "apps.accounts"
    # 应用标签：用于 Django 内部标识，区分其他 app
    label = "accounts"
    # 应用可读名称：在 Django 管理后台等处显示
    verbose_name = "Accounts"

    def ready(self):
        """
        Django App 初始化钩子：
        - 导入 signals 模块，确保用户相关信号（如创建、邮箱验证）在启动时注册
        - 不返回值，仅用于副作用注册
        """
        from . import signals  # noqa: F401  # 导入即触发信号注册，无需直接引用
        # 说明：此处仅为加载信号模块，无附加逻辑；若将来新增信号，保持导入即可生效
