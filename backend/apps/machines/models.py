from __future__ import annotations

from django.db import models
from django.conf import settings

# 模型定义：管理靶机实例生命周期（启动/关闭）、端口、动态 Flag 等

User = settings.AUTH_USER_MODEL
DEFAULT_CONTAINER_PORT = 80
DEFAULT_RUNTIME_MINUTES = getattr(settings, "MACHINE_MAX_RUNTIME_MINUTES", 30)


class ChallengeMachineConfig(models.Model):
    """
    题目级靶机配置：
    - 由出题人在后台录入靶机镜像/端口等模板信息
    - 实例启动时优先读取此配置，未配置则回退全局默认值
    """

    challenge = models.OneToOneField(
        "challenges.Challenge",
        verbose_name="题目",
        related_name="machine_config",
        on_delete=models.CASCADE,
        help_text="关联的题目，每题仅允许配置一份靶机模板",
    )
    image = models.CharField("容器镜像", max_length=255,
                             help_text="完整镜像名称，例如 registry.example.com/ftc/web:latest")
    container_port = models.PositiveIntegerField(
        "容器服务端口",
        default=DEFAULT_CONTAINER_PORT,
        help_text="镜像内部服务监听端口，用于主机端口映射",
    )
    max_instances_per_user = models.PositiveIntegerField(
        "单用户最大实例数",
        default=1,
        help_text="限制单个用户可同时运行的实例数量",
    )
    max_runtime_minutes = models.PositiveIntegerField(
        "实例最长运行分钟数",
        default=DEFAULT_RUNTIME_MINUTES,
        help_text="单个实例允许的最长运行时间，超过后将自动清理",
    )
    extend_minutes_default = models.PositiveIntegerField(
        "单次延时分钟数",
        default=30,
        help_text="用户点击延时追加的时间（分钟）",
    )
    extend_max_times = models.IntegerField(
        "最大延时次数",
        default=-1,
        help_text="每一实例允许用户延时的次数，-1 表示不限制，0 表示禁止延时。",
    )
    extend_threshold_minutes = models.IntegerField(
        "允许延时阈值（分钟）",
        default=15,
        help_text="仅当实例剩余时间小于等于该值时允许延时，0 或负数表示随时都可以延时",
    )
    clean_interval_seconds = models.PositiveIntegerField(
        "清理扫描间隔（秒）",
        default=300,
        help_text="Celery 清理任务扫描超时实例的频率",
    )
    port_cache_ttl = models.PositiveIntegerField(
        "端口占用缓存 TTL（秒）",
        default=300,
        help_text="端口占用在 Redis 中的缓存时间",
    )
    environment = models.JSONField(
        "环境变量",
        default=dict,
        blank=True,
        help_text="以 JSON 格式记录启动所需的环境变量键值对",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "题目靶机配置"
        verbose_name_plural = "题目靶机配置"

    def __str__(self) -> str:
        return f"{self.challenge.slug} -> {self.image}"


class MachineInstance(models.Model):
    """
    靶机实例：
    - 记录容器实例关联的比赛、题目、用户/队伍
    - 包含容器 ID、映射端口、动态 Flag 与状态，用于后续停止/销毁
    """

    class Status(models.TextChoices):
        """实例运行状态枚举：用于判断是否可重复启动/停止"""
        RUNNING = "running", "运行中"
        STOPPED = "stopped", "已停止"
        ERROR = "error", "异常"

    # 所属比赛
    contest = models.ForeignKey("contests.Contest", verbose_name="所属比赛", related_name="machines",
                                on_delete=models.CASCADE)
    # 关联题目
    challenge = models.ForeignKey("challenges.Challenge", verbose_name="题目", related_name="machines",
                                  on_delete=models.CASCADE)
    # 创建/启动者
    user = models.ForeignKey(User, verbose_name="用户", related_name="machines", on_delete=models.CASCADE)
    # 所在队伍，个人赛可为空
    team = models.ForeignKey("contests.Team", verbose_name="队伍", related_name="machines", on_delete=models.SET_NULL,
                             null=True, blank=True)
    # 容器 ID（由 docker_manager 返回）
    container_id = models.CharField("容器 ID", max_length=128, blank=True, default="")
    # 分配的主机地址
    host = models.CharField("主机地址", max_length=128, default="localhost")
    # 映射端口
    port = models.PositiveIntegerField("端口", null=True, blank=True)
    # 实例状态
    status = models.CharField("状态", max_length=20, choices=Status.choices, default=Status.RUNNING)
    # 延时次数
    extend_count = models.PositiveIntegerField("延时次数", default=0)
    # 过期时间（用于清理/倒计时）
    expires_at = models.DateTimeField("过期时间", null=True, blank=True)
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
