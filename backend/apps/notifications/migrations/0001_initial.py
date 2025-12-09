from __future__ import annotations

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings
from django.db.models import Q


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("contests", "0013_alter_contest_registration_start_time"),
        ("challenges", "0010_challenge_has_machine"),
    ]

    operations = [
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("type", models.CharField(choices=[("contest_new", "新比赛发布"), ("contest_registration_open", "报名开启"), ("contest_registration_deadline_soon", "报名截止前预警"), ("contest_registration_invalidated", "报名失效"), ("contest_upcoming", "即将开赛"), ("contest_started", "比赛开始"), ("contest_freeze_soon", "封榜前提醒"), ("contest_freeze", "封榜生效"), ("contest_ending_soon", "结束前提醒"), ("contest_ended", "比赛结束"), ("contest_announcement_new", "新公告"), ("challenge_new", "新题上线"), ("challenge_updated", "题目更新"), ("hint_unlocked", "提示已解锁"), ("team_member_joined", "队员加入"), ("team_member_left", "队员退出"), ("team_captain_transferred", "队长移交"), ("team_disbanded", "队伍解散"), ("team_invite_reset", "邀请码重置"), ("team_roster_warning", "队伍人数预警")], max_length=64, verbose_name="通知类型")),
                ("title", models.CharField(max_length=200, verbose_name="标题")),
                ("body", models.TextField(blank=True, default="", verbose_name="正文")),
                ("payload", models.JSONField(blank=True, default=dict, verbose_name="附加数据")),
                ("dedup_key", models.CharField(blank=True, db_index=True, default="", max_length=255, verbose_name="去重键")),
                ("read_at", models.DateTimeField(blank=True, null=True, verbose_name="已读时间")),
                ("expires_at", models.DateTimeField(blank=True, null=True, verbose_name="过期时间")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                ("challenge", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to="challenges.challenge", verbose_name="关联题目")),
                ("contest", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to="contests.contest", verbose_name="关联比赛")),
                ("team", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to="contests.team", verbose_name="关联队伍")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to=settings.AUTH_USER_MODEL, verbose_name="接收用户")),
            ],
            options={
                "verbose_name": "通知",
                "verbose_name_plural": "通知",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["user", "read_at"], name="notifications_user_read_idx"),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["user", "type", "created_at"], name="notifications_user_type_created_idx"),
        ),
        migrations.AddConstraint(
            model_name="notification",
            constraint=models.UniqueConstraint(condition=~Q(("dedup_key", "")), fields=("user", "dedup_key"), name="uniq_notification_user_dedup_key"),
        ),
    ]
