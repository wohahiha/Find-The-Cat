from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.db.models import Q

User = settings.AUTH_USER_MODEL


class Notification(models.Model):
    """
    系统通知模型：
    - 针对用户的私有通知，不持久化到公开频道
    - 关联比赛/队伍/题目，便于前端跳转
    """

    class Type(models.TextChoices):
        # 比赛相关
        CONTEST_NEW = "contest_new", "新比赛发布"
        CONTEST_REG_OPEN = "contest_registration_open", "报名开启"
        CONTEST_REG_DEADLINE_SOON = "contest_registration_deadline_soon", "报名截止前预警"
        CONTEST_REG_INVALIDATED = "contest_registration_invalidated", "报名失效"
        CONTEST_UPCOMING = "contest_upcoming", "即将开赛"
        CONTEST_STARTED = "contest_started", "比赛开始"
        CONTEST_FREEZE_SOON = "contest_freeze_soon", "封榜前提醒"
        CONTEST_FREEZE = "contest_freeze", "封榜生效"
        CONTEST_ENDING_SOON = "contest_ending_soon", "结束前提醒"
        CONTEST_ENDED = "contest_ended", "比赛结束"
        CONTEST_ANNOUNCEMENT_NEW = "contest_announcement_new", "新公告"
        # 题目/题库相关
        CHALLENGE_NEW = "challenge_new", "新题上线"
        CHALLENGE_UPDATED = "challenge_updated", "题目更新"
        HINT_UNLOCKED = "hint_unlocked", "提示已解锁"
        # 战队相关
        TEAM_MEMBER_JOINED = "team_member_joined", "队员加入"
        TEAM_MEMBER_LEFT = "team_member_left", "队员退出"
        TEAM_CAPTAIN_TRANSFERRED = "team_captain_transferred", "队长移交"
        TEAM_DISBANDED = "team_disbanded", "队伍解散"
        TEAM_INVITE_RESET = "team_invite_reset", "邀请码重置"
        TEAM_ROSTER_WARNING = "team_roster_warning", "队伍人数预警"
        # 靶机相关
        MACHINE_STARTED = "machine_started", "靶机启动"
        MACHINE_EXPIRING = "machine_expiring", "靶机即将到期"
        MACHINE_EXPIRED = "machine_expired", "靶机已回收"
        MACHINE_HEARTBEAT_MISS = "machine_heartbeat_miss", "靶机心跳异常"

    user = models.ForeignKey(User, verbose_name="接收用户", related_name="notifications", on_delete=models.CASCADE)
    type = models.CharField("通知类型", max_length=64, choices=Type.choices)
    contest = models.ForeignKey(
        "contests.Contest",
        verbose_name="关联比赛",
        related_name="notifications",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    team = models.ForeignKey(
        "contests.Team",
        verbose_name="关联队伍",
        related_name="notifications",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    challenge = models.ForeignKey(
        "challenges.Challenge",
        verbose_name="关联题目",
        related_name="notifications",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
    )
    title = models.CharField("标题", max_length=200)
    body = models.TextField("正文", blank=True, default="")
    payload = models.JSONField("附加数据", default=dict, blank=True)
    dedup_key = models.CharField("去重键", max_length=255, blank=True, default="", db_index=True)
    read_at = models.DateTimeField("已读时间", null=True, blank=True)
    expires_at = models.DateTimeField("过期时间", null=True, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "通知"
        verbose_name_plural = "通知"
        indexes = [
            models.Index(fields=["user", "read_at"]),
            models.Index(fields=["user", "type", "created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "dedup_key"],
                condition=~Q(dedup_key=""),
                name="uniq_notification_user_dedup_key",
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_type_display()} - {self.title}"

    @property
    def is_read(self) -> bool:
        return self.read_at is not None

    def mark_read(self) -> None:
        if self.read_at:
            return
        self.read_at = timezone.now()
        self.save(update_fields=["read_at"])
