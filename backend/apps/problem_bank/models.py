from __future__ import annotations

from django.db import models
from django.conf import settings
from django.utils import timezone
import hashlib
import hmac

from apps.common.security import get_flag_secret

# 模型层：题库、题库分类、题库题目与附件/提示/解题记录

User = settings.AUTH_USER_MODEL


class ProblemBank(models.Model):
    """题库主体：用于归档题目，支持公开/私有"""

    # 题库名称
    name = models.CharField("题库名称", max_length=200, unique=True)
    # 题库标识
    slug = models.SlugField("标识", max_length=200, unique=True)
    # 描述
    description = models.TextField("题库描述", blank=True)
    # 是否公开给前端浏览/作答
    is_public = models.BooleanField("是否公开", default=False)
    # 创建时间
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    # 更新时间
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ["-created_at", "name"]
        verbose_name = "题库"
        verbose_name_plural = "题库"

    def __str__(self) -> str:
        return self.name


class BankCategory(models.Model):
    """题库分类：便于题库内部对题目分组"""

    bank = models.ForeignKey(ProblemBank, verbose_name="所属题库", related_name="categories", on_delete=models.CASCADE)
    # 分类名称
    name = models.CharField("分类名称", max_length=80)
    # slug 用于标识
    slug = models.SlugField("标识", max_length=80)

    class Meta:
        unique_together = (("bank", "slug"), ("bank", "name"))
        ordering = ["name"]
        verbose_name = "题库分类"
        verbose_name_plural = "题库分类"

    def __str__(self) -> str:
        return f"{self.bank.name}:{self.name}"


class BankChallenge(models.Model):
    """
    题库题目：
    - 独立于比赛，不记录分值与计分模式，仅保留题面/Flag/附件/提示
    - 支持静态/动态 Flag；提示统一不扣分
    """

    class Difficulty(models.TextChoices):
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"
        HARD = "hard", "Hard"

    class FlagType(models.TextChoices):
        STATIC = "static", "静态 Flag"
        DYNAMIC = "dynamic", "动态 Flag"

    bank = models.ForeignKey(ProblemBank, verbose_name="所属题库", related_name="challenges", on_delete=models.CASCADE)
    category = models.ForeignKey(
        BankCategory, verbose_name="分类", related_name="challenges", on_delete=models.SET_NULL, null=True, blank=True
    )
    # 标题
    title = models.CharField("题目标题", max_length=200)
    # 唯一标识
    slug = models.SlugField("题目标识", max_length=200)
    # 简介
    short_description = models.CharField("题目简介", max_length=255, blank=True)
    # 题面
    content = models.TextField("题目内容")
    # 难度
    difficulty = models.CharField("难度", max_length=20, choices=Difficulty.choices, default=Difficulty.MEDIUM)
    # 标准 Flag 或种子
    flag = models.CharField("Flag", max_length=256)
    # Flag 忽略大小写
    flag_case_insensitive = models.BooleanField("忽略大小写", default=True)
    # Flag 类型
    flag_type = models.CharField("Flag 类型", max_length=16, choices=FlagType.choices, default=FlagType.STATIC)
    # Flag 前缀
    dynamic_prefix = models.CharField("Flag 前缀", max_length=64, blank=True, default="FLAG")
    # 是否可见
    is_active = models.BooleanField("是否可见", default=True)
    # 题目作者
    author = models.ForeignKey(User, verbose_name="作者", related_name="bank_challenges", on_delete=models.SET_NULL,
                               null=True)
    # 创建时间
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    # 更新时间
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        unique_together = (("bank", "slug"), ("bank", "title"))
        ordering = ["bank", "slug"]
        verbose_name = "题库题目"
        verbose_name_plural = "题库题目"

    def __str__(self) -> str:
        return f"{self.title} ({self.bank.name})"

    def normalized_flag(self, value: str) -> str:
        """按配置标准化输入 Flag，便于比对"""
        return value.strip().lower() if self.flag_case_insensitive else value.strip()

    def _assemble_flag(self, prefix: str, body: str) -> str:
        """拼接前缀与 flag 主体，形成标准串"""
        normalized_prefix = (prefix or "").strip()
        normalized_body = self.normalized_flag(body)
        wrapped = f"{normalized_prefix}{{{normalized_body}}}"
        return self.normalized_flag(wrapped)

    def build_expected_flag(self, user=None, secret: str | None = None) -> str:
        """构造当前用户的期望 Flag，动态题基于用户 ID 派生"""
        if self.flag_type != self.FlagType.DYNAMIC:
            return self._assemble_flag(self.dynamic_prefix, self.flag)
        owner_id = getattr(user, "id", None)
        if owner_id is None:
            return self._assemble_flag(self.dynamic_prefix, self.flag)
        flag_secret = secret or get_flag_secret()
        raw = f"{self.bank_id}:{self.id}:{owner_id}:{self.flag}"
        digest = hmac.new(flag_secret.encode("utf-8"), msg=raw.encode("utf-8"), digestmod=hashlib.sha256).hexdigest()[:32]
        return self._assemble_flag(self.dynamic_prefix, digest)

    def check_flag(self, submitted: str, *, user=None, secret: str | None = None) -> bool:
        """校验题库题目 Flag"""
        if self.flag_type == self.FlagType.DYNAMIC and user is None:
            return False
        expected = self.build_expected_flag(user=user, secret=secret)
        return self.normalized_flag(submitted) == expected


class BankAttachment(models.Model):
    """题库附件：存储下载链接"""

    challenge = models.ForeignKey(BankChallenge, verbose_name="题目", related_name="attachments",
                                  on_delete=models.CASCADE)
    name = models.CharField("附件名称", max_length=200)
    url = models.URLField("附件链接", max_length=500)
    order = models.PositiveIntegerField("排序", default=1)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "题库附件"
        verbose_name_plural = "题库附件"

    def __str__(self) -> str:
        return f"{self.challenge.slug} - {self.name}"


class BankHint(models.Model):
    """题库提示：统一免费，不扣分"""

    challenge = models.ForeignKey(BankChallenge, verbose_name="题目", related_name="hints", on_delete=models.CASCADE)
    title = models.CharField("提示标题", max_length=200)
    content = models.TextField("提示内容")
    order = models.PositiveIntegerField("排序", default=1)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "题库提示"
        verbose_name_plural = "题库提示"

    def __str__(self) -> str:
        return f"{self.challenge.slug} - {self.title}"


class BankSolve(models.Model):
    """题库解题记录：仅用于标记用户已完成，便于前端展示复盘状态"""

    challenge = models.ForeignKey(BankChallenge, verbose_name="题目", related_name="solves", on_delete=models.CASCADE)
    user = models.ForeignKey(User, verbose_name="用户", related_name="bank_solves", on_delete=models.CASCADE)
    solved_at = models.DateTimeField("解题时间", default=timezone.now)

    class Meta:
        unique_together = ("challenge", "user")
        ordering = ["solved_at"]
        indexes = [
            models.Index(fields=["challenge", "user"]),
        ]
        verbose_name = "题库解题记录"
        verbose_name_plural = "题库解题记录"

    def __str__(self) -> str:
        return f"{self.user} solved {self.challenge}"
