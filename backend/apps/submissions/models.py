from __future__ import annotations

from django.db import models
from django.conf import settings

# 模型定义：提交记录与判题结果，配合挑战模块的解题记录

User = settings.AUTH_USER_MODEL


class Submission(models.Model):
    """
    Flag 提交记录：
    - 关联比赛、题目、提交人及队伍
    - 记录提交的 Flag、判题状态、得分与可选的解题记录关联
    """

    class Status(models.TextChoices):
        """提交判题状态枚举：区分正确/错误/重复提交"""
        ACCEPTED = "accepted", "正确"
        REJECTED = "rejected", "错误"
        DUPLICATE = "duplicate", "重复提交"

    # 所属比赛
    contest = models.ForeignKey("contests.Contest", verbose_name="所属比赛", related_name="submissions",
                                on_delete=models.CASCADE)
    # 提交关联的题目
    challenge = models.ForeignKey("challenges.Challenge", verbose_name="题目", related_name="submissions",
                                  on_delete=models.CASCADE)
    # 提交人
    user = models.ForeignKey(User, verbose_name="用户", related_name="submissions", on_delete=models.CASCADE)
    # 提交人所在队伍（可为空，用于个人赛）
    team = models.ForeignKey("contests.Team", verbose_name="队伍", related_name="submissions",
                             on_delete=models.SET_NULL, null=True, blank=True)
    # 提交的原始 Flag
    flag_submitted = models.TextField("提交 Flag")
    # 判题状态
    status = models.CharField("状态", max_length=20, choices=Status.choices)
    # 是否正确
    is_correct = models.BooleanField("是否正确", default=False)
    # 判题消息（业务提示）
    message = models.CharField("提示", max_length=255, blank=True, default="")
    # 判定得分（正确时记录）
    awarded_points = models.PositiveIntegerField("得分", default=0)
    # 额外加分（n 血加分）
    bonus_points = models.PositiveIntegerField("额外加分", default=0)
    # 血次序（第几血），错误或重复为 0
    blood_rank = models.PositiveIntegerField("血次序", default=0)
    # 对应的解题记录（仅正确时关联）
    solve = models.ForeignKey("challenges.ChallengeSolve", verbose_name="解题记录", related_name="submissions",
                              on_delete=models.SET_NULL, null=True, blank=True)
    # 创建时间
    created_at = models.DateTimeField("提交时间", auto_now_add=True)
    # 判题时间
    judged_at = models.DateTimeField("判题时间", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["contest", "created_at"]),
            models.Index(fields=["challenge", "user"]),
            models.Index(fields=["challenge", "team"]),
        ]
        verbose_name = "Flag 提交"
        verbose_name_plural = "Flag 提交"

    def __str__(self) -> str:
        return f"{self.user} -> {self.challenge} ({self.status})"
