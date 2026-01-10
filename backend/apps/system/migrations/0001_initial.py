from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="SystemConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(db_index=True, max_length=120, unique=True, verbose_name="键")),
                ("value", models.TextField(verbose_name="配置值")),
                (
                    "value_type",
                    models.CharField(
                        choices=[
                            ("string", "字符串"),
                            ("int", "整数"),
                            ("bool", "布尔"),
                            ("json", "JSON"),
                            ("secret", "字符串"),
                        ],
                        default="string",
                        max_length=20,
                        verbose_name="值类型",
                    ),
                ),
                ("description", models.TextField(blank=True, verbose_name="说明")),
                ("is_active", models.BooleanField(default=True, verbose_name="启用覆盖")),
                (
                    "is_sensitive",
                    models.BooleanField(
                        default=False, help_text="后台仅展示脱敏值 ' *** '", verbose_name="敏感字段"
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
            ],
            options={"verbose_name": "系统配置", "verbose_name_plural": "系统配置", "ordering": ["key"]},
        ),
    ]
