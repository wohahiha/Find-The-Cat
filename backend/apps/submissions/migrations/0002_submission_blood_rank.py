from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('submissions', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='submission',
            name='blood_rank',
            field=models.PositiveIntegerField(default=0, verbose_name='血次序'),
        ),
    ]
