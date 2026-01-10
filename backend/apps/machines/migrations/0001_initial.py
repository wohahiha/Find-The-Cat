from __future__ import annotations

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("contests", "0003_contestannouncement"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("challenges", "0003_challengetask_challengeattachment_flagtype"),
    ]

    operations = [
        migrations.CreateModel(
            name="MachineInstance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("container_id", models.CharField(blank=True, default="", max_length=128, verbose_name="容器 ID")),
                ("host", models.CharField(default="localhost", max_length=128, verbose_name="主机地址")),
                ("port", models.PositiveIntegerField(blank=True, null=True, verbose_name="端口")),
                ("dynamic_flag", models.CharField(blank=True, default="", max_length=256, verbose_name="动态 Flag")),
                ("status", models.CharField(choices=[("running", "运行中"), ("stopped", "已停止"), ("error", "异常")], default="running", max_length=20, verbose_name="状态")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                ("challenge", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="machines", to="challenges.challenge", verbose_name="题目")),
                ("contest", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="machines", to="contests.contest", verbose_name="所属比赛")),
                ("team", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="machines", to="contests.team", verbose_name="队伍")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="machines", to=settings.AUTH_USER_MODEL, verbose_name="用户")),
            ],
            options={
                "verbose_name": "靶机实例",
                "verbose_name_plural": "靶机实例",
                "ordering": ["-created_at"],
            },
        ),
    ]
