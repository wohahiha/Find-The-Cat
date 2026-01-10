from __future__ import annotations

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("contests", "0002_alter_contest_created_at_alter_contest_description_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ContestAnnouncement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200, verbose_name="公告标题")),
                ("content", models.TextField(verbose_name="公告内容")),
                ("is_active", models.BooleanField(default=True, verbose_name="是否生效")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                (
                    "contest",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="announcements",
                        to="contests.contest",
                        verbose_name="所属比赛",
                    ),
                ),
            ],
            options={
                "verbose_name": "比赛公告",
                "verbose_name_plural": "比赛公告",
                "ordering": ["-created_at"],
            },
        ),
    ]
