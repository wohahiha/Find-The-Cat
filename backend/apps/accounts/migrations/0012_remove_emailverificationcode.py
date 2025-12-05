# Generated manually for EmailVerificationCode migration from accounts to system

from django.db import migrations


class Migration(migrations.Migration):
    """
    从 accounts 模块移除 EmailVerificationCode 模型

    策略：
    - 只从 Django 状态中删除模型，不删除数据库表
    - 表 accounts_emailverificationcode 仍然存在，现在由 system.EmailVerificationCode 管理
    """

    dependencies = [
        ('accounts', '0011_delete_mailaccount'),
    ]

    operations = [
        # 使用 SeparateDatabaseAndState 只在状态中删除，不删除表
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(
                    name='EmailVerificationCode',
                ),
            ],
            # 数据库操作为空：保留表，由 system 模块管理
            database_operations=[],
        ),
    ]
