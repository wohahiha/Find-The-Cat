from __future__ import annotations

from django.db import models
from django.conf import settings
from django.utils import timezone

# 模型文件：定义题目、分类、解题记录及子任务/附件的数据结构，不承载业务流程。

User = settings.AUTH_USER_MODEL


class ChallengeCategory(models.Model):
    """
    题目分类：
    - 供题目归类与前端过滤使用。
    """

    # 分类名称
    name = models.CharField("分类名称", max_length=80, unique=True)
    # 分类标识 slug
    slug = models.SlugField("分类标识", max_length=80, unique=True)
    # 分类描述
    description = models.TextField("分类描述", blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "题目分类"
        verbose_name_plural = "题目分类"

    def __str__(self) -> str:
        return self.name


class Challenge(models.Model):
    """
    题目主体：
    - 关联比赛与分类，记录题面、Flag 信息及分值。
    - 支持静态/动态 Flag 与大小写控制。
    """

    class Difficulty(models.TextChoices):
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"
        HARD = "hard", "Hard"

    # 所属比赛
    contest = models.ForeignKey("contests.Contest", verbose_name="所属比赛", related_name="challenges", on_delete=models.CASCADE)
    # 分类，可为空
    category = models.ForeignKey(ChallengeCategory, verbose_name="分类", related_name="challenges", on_delete=models.SET_NULL, null=True)
    # 题目标题
    title = models.CharField("题目标题", max_length=200)
    # 题目标识 slug
    slug = models.SlugField("题目标识", max_length=200)
    # 题目简介
    short_description = models.CharField("题目简介", max_length=255, blank=True)
    # 题目内容（题面）
    content = models.TextField("题目内容")
    # 难度枚举
    difficulty = models.CharField("难度", max_length=20, choices=Difficulty.choices, default=Difficulty.MEDIUM)
    # 基础分值
    base_points = models.PositiveIntegerField("基础分值", default=100)
    class FlagType(models.TextChoices):
        STATIC = "static", "静态 Flag"
        DYNAMIC = "dynamic", "动态 Flag"

    # 标准 Flag（静态或动态前缀）
    flag = models.CharField("Flag", max_length=256)
    # Flag 是否忽略大小写
    flag_case_insensitive = models.BooleanField("忽略大小写", default=True)
    # Flag 类型：静态/动态
    flag_type = models.CharField("Flag 类型", max_length=16, choices=FlagType.choices, default=FlagType.STATIC)
    # 动态 Flag 前缀，占位字段
    dynamic_prefix = models.CharField("动态 Flag 前缀", max_length=64, blank=True)
    # 是否开放作答
    is_active = models.BooleanField("是否开放", default=True)
    # 出题人
    author = models.ForeignKey(User, verbose_name="出题人", related_name="challenges", on_delete=models.SET_NULL, null=True)
    # 创建时间
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    # 更新时间
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        unique_together = (("contest", "slug"), ("contest", "title"))
        ordering = ["contest", "slug"]
        verbose_name = "题目"
        verbose_name_plural = "题目"

    def __str__(self) -> str:
        return f"{self.title} ({self.contest.slug})"

    def normalized_flag(self, value: str) -> str:
        """按配置标准化输入 Flag（去空格/大小写）。"""
        return value.strip().lower() if self.flag_case_insensitive else value.strip()

    def check_flag(self, submitted: str) -> bool:
        """
        Flag 校验：
        - 静态模式：直接比对标准化后的 flag。
        - 动态模式：当前版本仅比对前缀并回退标准化比较，未来可对接动态 flag 生成服务。
        """
        if self.flag_type == self.FlagType.DYNAMIC:
            # 动态模式占位：若配置前缀则需匹配前缀；其余部分暂与 flag 标准化比较
            if self.dynamic_prefix and not submitted.startswith(self.dynamic_prefix):
                return False
            # TODO: 对接动态 flag 生成与验证逻辑
        return self.normalized_flag(submitted) == self.normalized_flag(self.flag)


class ChallengeSolve(models.Model):
    """
    解题记录：
    - 记录选手或队伍的解题得分及时间，用于榜单统计。
    """

    # 题目外键
    challenge = models.ForeignKey(Challenge, verbose_name="题目", related_name="solves", on_delete=models.CASCADE)
    # 解题用户
    user = models.ForeignKey(User, verbose_name="选手", related_name="challenge_solves", on_delete=models.CASCADE)
    # 解题队伍，可为空（个人赛）
    team = models.ForeignKey("contests.Team", verbose_name="队伍", related_name="challenge_solves", on_delete=models.SET_NULL, null=True, blank=True)
    # 最终得分（含动态计分时可能调整）
    awarded_points = models.PositiveIntegerField("得分", default=0)
    # 解题时间戳
    solved_at = models.DateTimeField("解题时间", default=timezone.now)

    class Meta:
        unique_together = ("challenge", "user")
        ordering = ["solved_at"]
        verbose_name = "解题记录"
        verbose_name_plural = "解题记录"

    def __str__(self) -> str:
        return f"{self.user} solved {self.challenge}"


class ChallengeTask(models.Model):
    """题目子任务：用于多阶段得分或提示指引。"""

    # 关联题目
    challenge = models.ForeignKey(Challenge, verbose_name="题目", related_name="tasks", on_delete=models.CASCADE)
    # 子任务标题
    title = models.CharField("子任务标题", max_length=200)
    # 子任务描述
    description = models.TextField("子任务描述", blank=True)
    # 子任务分值
    points = models.PositiveIntegerField("子任务分值", default=0)
    # 排序字段
    order = models.PositiveIntegerField("排序", default=1)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "题目子任务"
        verbose_name_plural = "题目子任务"

    def __str__(self) -> str:
        return f"{self.challenge.slug} - {self.title}"


class ChallengeAttachment(models.Model):
    """题目附件：记录可下载的附件链接。"""

    # 关联题目
    challenge = models.ForeignKey(Challenge, verbose_name="题目", related_name="attachments", on_delete=models.CASCADE)
    # 附件名称
    name = models.CharField("附件名称", max_length=200)
    # 附件下载链接
    url = models.URLField("附件链接", max_length=500)
    # 排序字段
    order = models.PositiveIntegerField("排序", default=1)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "题目附件"
        verbose_name_plural = "题目附件"

    def __str__(self) -> str:
        return f"{self.challenge.slug} - {self.name}"
