from __future__ import annotations

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("contests", "0003_contestannouncement"),
        ("challenges", "0002_alter_challenge_author_alter_challenge_base_points_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="challenge",
            name="dynamic_prefix",
            field=models.CharField(blank=True, max_length=64, verbose_name="动态 Flag 前缀"),
        ),
        migrations.AddField(
            model_name="challenge",
            name="flag_type",
            field=models.CharField(
                choices=[("static", "静态 Flag"), ("dynamic", "动态 Flag")],
                default="static",
                max_length=16,
                verbose_name="Flag 类型",
            ),
        ),
        migrations.CreateModel(
            name="ChallengeAttachment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200, verbose_name="附件名称")),
                ("url", models.URLField(max_length=500, verbose_name="附件链接")),
                ("order", models.PositiveIntegerField(default=1, verbose_name="排序")),
                (
                    "challenge",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attachments",
                        to="challenges.challenge",
                        verbose_name="题目",
                    ),
                ),
            ],
            options={
                "verbose_name": "题目附件",
                "verbose_name_plural": "题目附件",
                "ordering": ["order", "id"],
            },
        ),
        migrations.CreateModel(
            name="ChallengeTask",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200, verbose_name="子任务标题")),
                ("description", models.TextField(blank=True, verbose_name="子任务描述")),
                ("points", models.PositiveIntegerField(default=0, verbose_name="子任务分值")),
                ("order", models.PositiveIntegerField(default=1, verbose_name="排序")),
                (
                    "challenge",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tasks",
                        to="challenges.challenge",
                        verbose_name="题目",
                    ),
                ),
            ],
            options={
                "verbose_name": "题目子任务",
                "verbose_name_plural": "题目子任务",
                "ordering": ["order", "id"],
            },
        ),
    ]
