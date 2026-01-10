# Generated manually for EmailVerificationCode migration from accounts to system

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    EmailVerificationCode 模型物理迁移：从 accounts 迁移到 system

    策略：
    1. EmailVerificationCode: 表已存在（accounts_emailverificationcode），只需在 Django 状态中创建模型，不创建表
    2. AdminActionLog: 新模型，正常创建表
    3. SystemLog: 非数据库模型（managed=False），只在 Django 状态中存在
    4. SystemConfig: 更新 verbose_name_plural
    """

    dependencies = [
        ('configs', '0009_copy_mailaccount_data'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. 更新 SystemConfig 的 Meta 选项
        migrations.AlterModelOptions(
            name='systemconfig',
            options={
                'ordering': ['key'],
                'verbose_name': 'SYSTEM',
                'verbose_name_plural': '系统配置'
            },
        ),

        # 2. 创建 SystemLog 模型（managed=False，不创建表）
        migrations.CreateModel(
            name='SystemLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.CharField(max_length=50, verbose_name='时间')),
                ('level', models.CharField(max_length=20, verbose_name='级别')),
                ('logger', models.CharField(max_length=100, verbose_name='记录器')),
                ('message', models.TextField(verbose_name='消息')),
                ('request_id', models.CharField(blank=True, max_length=50, verbose_name='请求ID')),
                ('user_id', models.CharField(blank=True, max_length=50, verbose_name='用户ID')),
                ('ip', models.CharField(blank=True, max_length=50, verbose_name='IP地址')),
                ('path', models.CharField(blank=True, max_length=200, verbose_name='路径')),
                ('method', models.CharField(blank=True, max_length=10, verbose_name='方法')),
                ('user_agent', models.CharField(blank=True, max_length=200, verbose_name='User-Agent')),
                ('raw_line', models.TextField(blank=True, verbose_name='原始日志')),
            ],
            options={
                'verbose_name': 'SYSTEM',
                'verbose_name_plural': '系统日志',
                'db_table': 'system_log_view',
                'managed': False,
            },
        ),

        # 3. EmailVerificationCode: 使用 SeparateDatabaseAndState 只在状态中创建，不创建表
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='EmailVerificationCode',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('email', models.EmailField(max_length=254, verbose_name='邮箱')),
                        ('scene', models.CharField(
                            choices=[
                                ('register', '注册'),
                                ('reset_password', '找回密码'),
                                ('bind_email', '绑定邮箱')
                            ],
                            max_length=32,
                            verbose_name='场景'
                        )),
                        ('code', models.CharField(max_length=6, verbose_name='验证码')),
                        ('is_used', models.BooleanField(default=False, verbose_name='是否已使用')),
                        ('expires_at', models.DateTimeField(verbose_name='过期时间')),
                        ('verified_at', models.DateTimeField(blank=True, null=True, verbose_name='验证时间')),
                        ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                        ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                    ],
                    options={
                        'verbose_name': 'SYSTEM',
                        'verbose_name_plural': '系统日志 - 邮箱验证码',
                        'db_table': 'accounts_emailverificationcode',
                        'ordering': ['-created_at'],
                        'indexes': [
                            models.Index(fields=['email', 'scene', 'is_used'], name='accounts_em_email_24d9bc_idx'),
                            models.Index(fields=['scene', 'created_at'], name='accounts_em_scene_99be2c_idx')
                        ],
                    },
                ),
            ],
            # 数据库操作为空：表已存在，不需要创建
            database_operations=[],
        ),

        # 4. AdminActionLog: 正常创建新表
        migrations.CreateModel(
            name='AdminActionLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('username', models.CharField(help_text='操作人用户名快照', max_length=150, verbose_name='用户名')),
                ('action_type', models.CharField(
                    choices=[
                        ('create', '创建'),
                        ('update', '修改'),
                        ('delete', '删除')
                    ],
                    max_length=10,
                    verbose_name='操作类型'
                )),
                ('content_type', models.CharField(help_text='例如：User, Contest, Challenge', max_length=100, verbose_name='模型类型')),
                ('object_id', models.CharField(blank=True, help_text='被操作对象的ID', max_length=100, verbose_name='对象ID')),
                ('object_repr', models.CharField(help_text='被操作对象的字符串表示', max_length=200, verbose_name='对象描述')),
                ('changes', models.JSONField(blank=True, help_text='操作前后的数据对比（JSON格式）', null=True, verbose_name='变更详情')),
                ('message', models.TextField(blank=True, help_text='操作的详细说明或备注', verbose_name='操作说明')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP地址')),
                ('user_agent', models.CharField(blank=True, max_length=255, verbose_name='User-Agent')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='操作时间')),
                ('user', models.ForeignKey(
                    help_text='执行操作的管理员',
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='操作人'
                )),
            ],
            options={
                'verbose_name': 'SYSTEM',
                'verbose_name_plural': '系统日志 - 管理员操作',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['user', 'created_at'], name='configs_adm_user_id_c85f77_idx'),
                    models.Index(fields=['action_type', 'created_at'], name='configs_adm_action__9aebdb_idx'),
                    models.Index(fields=['content_type', 'created_at'], name='configs_adm_content_ea9eec_idx')
                ],
            },
        ),
    ]
