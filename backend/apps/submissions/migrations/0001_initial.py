from __future__ import annotations

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("accounts", "0007_ensure_default_groups_permissions"),
        ("contests", "0003_contestannouncement"),
        ("challenges", "0003_challengetask_challengeattachment_flagtype"),
    ]

    operations = [
        migrations.CreateModel(
            name="Submission",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("flag_submitted", models.TextField(verbose_name="提交 Flag")),
                ("status", models.CharField(choices=[("accepted", "正确"), ("rejected", "错误"), ("duplicate", "重复提交")], max_length=20, verbose_name="状态")),
                ("is_correct", models.BooleanField(default=False, verbose_name="是否正确")),
                ("message", models.CharField(blank=True, default="", max_length=255, verbose_name="提示")),
                ("awarded_points", models.PositiveIntegerField(default=0, verbose_name="得分")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="提交时间")),
                ("judged_at", models.DateTimeField(auto_now_add=True, verbose_name="判题时间")),
                ("challenge", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="submissions", to="challenges.challenge", verbose_name="题目")),
                ("contest", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="submissions", to="contests.contest", verbose_name="所属比赛")),
                ("solve", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="submissions", to="challenges.challengesolve", verbose_name="解题记录")),
                ("team", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="submissions", to="contests.team", verbose_name="队伍")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="submissions", to="accounts.user", verbose_name="用户")),
            ],
            options={
                "verbose_name": "Flag 提交",
                "verbose_name_plural": "Flag 提交",
                "ordering": ["-created_at"],
            },
        ),
    ]
