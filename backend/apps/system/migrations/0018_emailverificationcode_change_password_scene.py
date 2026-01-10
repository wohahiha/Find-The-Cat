from django.db import migrations, models


class Migration(migrations.Migration):
    """
    为邮箱验证码增加修改密码场景：
    - 新增 change_password 场景选项，支持修改密码时的邮箱验证
    """

    dependencies = [
        ("configs", "0017_mailaccount_verification_expire_minutes"),
    ]

    operations = [
        migrations.AlterField(
            model_name="emailverificationcode",
            name="scene",
            field=models.CharField(
                choices=[
                    ("register", "注册"),
                    ("reset_password", "找回密码"),
                    ("bind_email", "绑定邮箱"),
                    ("change_password", "修改密码"),
                ],
                max_length=32,
                verbose_name="场景",
            ),
        ),
    ]
