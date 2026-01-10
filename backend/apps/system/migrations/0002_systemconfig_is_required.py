from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("configs", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="systemconfig",
            name="is_required",
            field=models.BooleanField(
                default=False,
                help_text="此配置为必填项，缺失可能导致平台不可用",
                verbose_name="必填",
            ),
        ),
    ]
