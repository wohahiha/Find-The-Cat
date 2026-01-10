from __future__ import annotations

from django.db import models
from django.utils import timezone
from django.conf import settings
from django.utils.text import slugify

# 模型文件：负责比赛、公告、队伍与队员的数据结构定义，不承载业务流程

User = settings.AUTH_USER_MODEL


class Contest(models.Model):
    """
    比赛模型：
    - 覆盖比赛的核心信息（名称、时间、可见性、赛制）
    - 提供比赛状态辅助属性，用于服务层校验比赛是否可报名/计分
    """

    class Visibility(models.TextChoices):
        """比赛可见性枚举：控制公开/私有访问范围"""
        PUBLIC = "public", "公开"
        PRIVATE = "private", "私有"

    # 比赛名称
    name = models.CharField("比赛名称", max_length=200)
    # 唯一标识，供路由与接口访问
    slug = models.SlugField("标识", max_length=200, unique=True)
    # 比赛描述，富文本可由前端渲染
    description = models.TextField("比赛描述", blank=True)
    # 可见性：公开/私有
    visibility = models.CharField("可见性", max_length=20, choices=Visibility.choices, default=Visibility.PUBLIC)
    # 开赛时间
    start_time = models.DateTimeField("开始时间")
    # 结束时间
    end_time = models.DateTimeField("结束时间")
    # 封榜时间，可为空
    freeze_time = models.DateTimeField("封榜时间", null=True, blank=True)
    # 报名开始时间，可为空表示立即开放
    registration_start_time = models.DateTimeField(
        "报名开始时间",
        null=True,
        blank=True,
        help_text="设置后不可再调整，如需变更请联系管理员重置比赛",
    )
    # 报名截止时间，可为空表示一直开放至开赛
    registration_end_time = models.DateTimeField("报名截止时间", null=True, blank=True)
    # 团队赛 / 个人赛
    is_team_based = models.BooleanField("团队赛", default=True)
    # 队伍人数上限
    max_team_members = models.PositiveIntegerField("队伍人数上限", default=4)
    # 记录创建时间
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    # 记录更新时间
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ["-start_time", "name"]
        verbose_name = "比赛"
        verbose_name_plural = "比赛"

    def __str__(self) -> str:
        return self.name

    @property
    def is_active(self) -> bool:
        """比赛是否进行中：用于接口展示和状态校验"""
        now = timezone.now()
        return self.start_time <= now <= self.end_time

    @property
    def has_started(self) -> bool:
        """是否已开赛，供报名/提交校验"""
        return timezone.now() >= self.start_time

    @property
    def has_ended(self) -> bool:
        """是否已结束，供禁止后续操作"""
        return timezone.now() > self.end_time


class ContestScoreboard(Contest):
    """
    比赛排行榜代理模型：
    - 仅用于 Django Admin 展示排行榜，不新增数据库表
    - 复用 Contest 数据，提供后台排行榜视图
    """

    class Meta:
        proxy = True
        verbose_name = "排行榜"
        verbose_name_plural = "排行榜"


class ContestAnnouncement(models.Model):
    """
    比赛公告模型：
    - 关联比赛的公告信息，支持前台拉取
    - is_active 控制公告是否展示
    """

    # 所属比赛
    contest = models.ForeignKey(Contest, verbose_name="所属比赛", related_name="announcements",
                                on_delete=models.CASCADE)
    # 公告标题
    title = models.CharField("公告标题", max_length=200)
    # 公告摘要（首页/列表使用，必填）
    summary = models.CharField("公告摘要", max_length=500)
    # 公告正文
    content = models.TextField("公告内容")
    # 是否展示
    is_active = models.BooleanField("是否生效", default=True)
    # 创建时间戳
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    # 更新时间戳
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["contest", "is_active", "created_at"]),
        ]
        verbose_name = "公告"
        verbose_name_plural = "公告"

    def __str__(self) -> str:
        return f"{self.contest.slug}: {self.title}"


def default_invite_token() -> str:
    """默认邀请码生成器：使用时间戳 slug，保证初始可用"""
    return slugify(timezone.now().isoformat())[:12]


class Team(models.Model):
    """
    队伍模型：
    - 关联比赛，记录队伍基本信息与队长
    - invite_token 用于加入队伍的凭证
    """

    # 所属比赛
    contest = models.ForeignKey(Contest, verbose_name="所属比赛", related_name="teams", on_delete=models.CASCADE)
    # 队伍名称
    name = models.CharField("队伍名称", max_length=120)
    # 队伍标识，便于展示/路由
    slug = models.SlugField("队伍标识", max_length=150)
    # 队伍简介
    description = models.TextField("简介", blank=True)
    # 队伍邀请码，唯一约束
    invite_token = models.CharField("邀请码", max_length=32, default=default_invite_token, unique=True)
    # 队长用户外键
    captain = models.ForeignKey(User, verbose_name="队长", related_name="owned_teams", on_delete=models.CASCADE)
    # 队伍是否有效（解散后置为 False）
    is_active = models.BooleanField("有效", default=True)
    # 创建时间
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    # 更新时间
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        unique_together = (
            ("contest", "name"),
            ("contest", "slug"),
        )
        ordering = ["name"]
        verbose_name = "队伍"
        verbose_name_plural = "队伍"

    def __str__(self) -> str:
        return f"{self.name} ({self.contest.name})"

    @property
    def member_count(self) -> int:
        """当前有效成员数量，用于人数上限校验"""
        return self.members.filter(is_active=True).count()  # type: ignore[attr-defined]


class TeamMember(models.Model):
    """
    队伍成员模型：
    - 描述队伍与用户的多对多关系
    - role 标识角色（队长/队员），is_active 控制是否在队伍中
    """

    class Role(models.TextChoices):
        """队伍成员角色枚举：区分队长与普通队员"""
        CAPTAIN = "captain", "队长"
        MEMBER = "member", "队员"

    # 关联队伍
    team = models.ForeignKey(Team, verbose_name="队伍", related_name="members", on_delete=models.CASCADE)
    # 关联用户
    user = models.ForeignKey(User, verbose_name="用户", related_name="team_memberships", on_delete=models.CASCADE)
    # 成员角色
    role = models.CharField("角色", max_length=20, choices=Role.choices, default=Role.MEMBER)
    # 加入时间
    joined_at = models.DateTimeField("加入时间", auto_now_add=True)
    # 是否有效（退出/解散后置为 False）
    is_active = models.BooleanField("有效", default=True)

    class Meta:
        unique_together = ("team", "user")
        indexes = [
            models.Index(fields=["team", "is_active"]),
            models.Index(fields=["team", "user", "is_active"]),
        ]
        verbose_name = "参赛队伍成员"
        verbose_name_plural = "参赛队伍成员"

    def __str__(self) -> str:
        return f"{self.user} -> {self.team}"


class ContestParticipant(models.Model):
    """
    比赛参与记录：
    - 记录用户在某场比赛的参与状态（已报名/进行中/已结束）
    - 便于后台筛选、展示参赛选手列表
    """

    class Status(models.TextChoices):
        """参与状态枚举"""
        REGISTERED = "registered", "已报名"
        RUNNING = "running", "进行中"
        FINISHED = "finished", "已结束"

    contest = models.ForeignKey(Contest, verbose_name="比赛", related_name="participants", on_delete=models.CASCADE)
    user = models.ForeignKey(User, verbose_name="用户", related_name="contest_participations", on_delete=models.CASCADE)
    status = models.CharField("状态", max_length=20, choices=Status.choices, default=Status.REGISTERED)
    is_valid = models.BooleanField("报名有效", default=True)
    created_at = models.DateTimeField("记录创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        unique_together = ("contest", "user")
        indexes = [
            models.Index(fields=["contest", "status"]),
            models.Index(fields=["user", "status"]),
        ]
        verbose_name = "比赛参与记录"
        verbose_name_plural = "比赛参与记录"

    def __str__(self) -> str:
        return f"{self.user} @ {self.contest} ({self.get_status_display()})"  # type: ignore[attr-defined]
