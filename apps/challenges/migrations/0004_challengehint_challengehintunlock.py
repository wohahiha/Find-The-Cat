from __future__ import annotations

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ("contests", "0003_contestannouncement"),
        ("challenges", "0003_challengetask_challengeattachment_flagtype"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ChallengeHint",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200, verbose_name="提示标题")),
                ("content", models.TextField(verbose_name="提示内容")),
                ("is_free", models.BooleanField(default=True, verbose_name="是否免费")),
                ("cost", models.PositiveIntegerField(default=0, verbose_name="扣分成本")),
                ("order", models.PositiveIntegerField(default=1, verbose_name="排序")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                (
                    "challenge",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="hints",
                        to="challenges.challenge",
                        verbose_name="题目",
                    ),
                ),
            ],
            options={
                "verbose_name": "题目提示",
                "verbose_name_plural": "题目提示",
                "ordering": ["order", "id"],
            },
        ),
        migrations.CreateModel(
            name="ChallengeHintUnlock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("cost", models.PositiveIntegerField(default=0, verbose_name="扣分成本")),
                ("unlocked_at", models.DateTimeField(auto_now_add=True, verbose_name="解锁时间")),
                (
                    "challenge",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="hint_unlocks",
                        to="challenges.challenge",
                        verbose_name="题目",
                    ),
                ),
                (
                    "hint",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="unlocks",
                        to="challenges.challengehint",
                        verbose_name="提示",
                    ),
                ),
                (
                    "team",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="hint_unlocks",
                        to="contests.team",
                        verbose_name="队伍",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="hint_unlocks",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="用户",
                    ),
                ),
            ],
            options={
                "verbose_name": "提示解锁",
                "verbose_name_plural": "提示解锁",
                "ordering": ["-unlocked_at"],
                "unique_together": {("hint", "user")},
            },
        ),
    ]
