from django.db import migrations


class Migration(migrations.Migration):
    """
    合并迁移：解决 0002_remove_systemconfig_is_active 与 0002_systemconfig_is_required 冲突
    """

    dependencies = [
        ("configs", "0002_remove_systemconfig_is_active"),
        ("configs", "0002_systemconfig_is_required"),
    ]

    operations = []

