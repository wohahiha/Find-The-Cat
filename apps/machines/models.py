from __future__ import annotations

from django.db import models
from django.conf import settings

# 模型定义：管理靶机实例生命周期（启动/关闭）、端口、动态 Flag 等。

User = settings.AUTH_USER_MODEL


class MachineInstance(models.Model):
    """
    靶机实例：
    - 记录容器实例关联的比赛、题目、用户/队伍。
    - 包含容器 ID、映射端口、动态 Flag 与状态，用于后续停止/销毁。
    """

    class Status(models.TextChoices):
        """实例运行状态枚举：用于判断是否可重复启动/停止。"""
        RUNNING = "running", "运行中"
        STOPPED = "stopped", "已停止"
        ERROR = "error", "异常"

    # 所属比赛
    contest = models.ForeignKey("contests.Contest", verbose_name="所属比赛", related_name="machines", on_delete=models.CASCADE)
    # 关联题目
    challenge = models.ForeignKey("challenges.Challenge", verbose_name="题目", related_name="machines", on_delete=models.CASCADE)
    # 创建/启动者
    user = models.ForeignKey(User, verbose_name="用户", related_name="machines", on_delete=models.CASCADE)
    # 所在队伍，个人赛可为空
    team = models.ForeignKey("contests.Team", verbose_name="队伍", related_name="machines", on_delete=models.SET_NULL, null=True, blank=True)
    # 容器 ID（由 docker_manager 返回）
    container_id = models.CharField("容器 ID", max_length=128, blank=True, default="")
    # 分配的主机地址
    host = models.CharField("主机地址", max_length=128, default="localhost")
    # 映射端口
    port = models.PositiveIntegerField("端口", null=True, blank=True)
    # 实例状态
    status = models.CharField("状态", max_length=20, choices=Status.choices, default=Status.RUNNING)
    # 启动时间
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    # 更新时间
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["contest", "challenge", "user", "status"]),
            models.Index(fields=["port"]),
        ]
        verbose_name = "靶机实例"
        verbose_name_plural = "靶机实例"

    def __str__(self) -> str:
        return f"{self.challenge.slug} @ {self.host}:{self.port or '-'} ({self.status})"
