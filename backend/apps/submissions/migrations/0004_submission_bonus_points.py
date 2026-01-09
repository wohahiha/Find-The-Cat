from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("submissions", "0003_submission_submissions_contest_fb4c14_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="submission",
            name="bonus_points",
            field=models.PositiveIntegerField(default=0, verbose_name="额外加分"),
        ),
    ]
