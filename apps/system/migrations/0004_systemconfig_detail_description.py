from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("configs", "0003_merge_0002_remove_systemconfig_is_active_0002_systemconfig_is_required"),
    ]

    operations = [
        migrations.AddField(
            model_name="systemconfig",
            name="detail_description",
            field=models.TextField(verbose_name="详细用途说明", blank=True, default=""),
        ),
    ]
