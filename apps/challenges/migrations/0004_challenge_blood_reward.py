from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("challenges", "0006_alter_challenge_dynamic_prefix_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="challenge",
            name="blood_bonus_points",
            field=models.JSONField(blank=True, default=list, verbose_name="n血加分列表"),
        ),
        migrations.AddField(
            model_name="challenge",
            name="blood_reward_count",
            field=models.PositiveIntegerField(default=0, verbose_name="n血数量"),
        ),
        migrations.AddField(
            model_name="challenge",
            name="blood_reward_type",
            field=models.CharField(
                choices=[("none", "无奖励"), ("bonus", "加分奖励"), ("no_decay", "前 n 血不衰减")],
                default="none",
                max_length=16,
                verbose_name="n血奖励类型",
            ),
        ),
        migrations.AddField(
            model_name="challengesolve",
            name="bonus_points",
            field=models.PositiveIntegerField(default=0, verbose_name="额外加分"),
        ),
    ]
