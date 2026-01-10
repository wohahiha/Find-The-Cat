from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0007_ensure_default_groups_permissions'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='is_team_leader',
        ),
        migrations.RemoveField(
            model_name='user',
            name='team_uuid',
        ),
    ]
