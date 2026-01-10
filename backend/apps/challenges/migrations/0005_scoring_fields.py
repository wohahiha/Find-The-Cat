from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("challenges", "0004_challengehint_challengehintunlock"),
    ]

    operations = [
        migrations.AddField(
            model_name="challenge",
            name="decay_factor",
            field=models.FloatField(default=0.95, verbose_name="衰减因子"),
        ),
        migrations.AddField(
            model_name="challenge",
            name="decay_type",
            field=models.CharField(
                choices=[("percentage", "按百分比衰减"), ("fixed_step", "固定分值递减")],
                default="percentage",
                max_length=16,
                verbose_name="衰减类型",
            ),
        ),
        migrations.AddField(
            model_name="challenge",
            name="min_score",
            field=models.PositiveIntegerField(default=50, verbose_name="最低分"),
        ),
        migrations.AddField(
            model_name="challenge",
            name="scoring_mode",
            field=models.CharField(
                choices=[("fixed", "固定分值"), ("dynamic", "动态分值")],
                default="fixed",
                max_length=16,
                verbose_name="计分模式",
            ),
        ),
    ]
