from __future__ import annotations

from django.db import models
from django.conf import settings
from django.utils import timezone
import hashlib
import hmac

# 模型文件：定义题目、分类、解题记录及子任务/附件/提示的数据结构，不承载业务流程
from apps.common.security import get_flag_secret

User = settings.AUTH_USER_MODEL


class ChallengeCategory(models.Model):
    """
    题目分类：
    - 业务场景：对比赛题目进行分类，便于前端筛选/统计
    - 模块角色：按比赛维度维护分类表，被题目外键引用
    """

    # 所属比赛
    contest = models.ForeignKey(
        "contests.Contest",
        verbose_name="所属比赛",
        related_name="challenge_categories",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="分类归属的比赛，只能在该比赛内使用",
    )
    # 分类名称
    name = models.CharField("分类名称", max_length=80, help_text="分类显示名称，后台与前台保持一致")
    # 分类标识 slug
    slug = models.SlugField("分类标识", max_length=80, help_text="分类唯一标识，供接口/URL 使用")
    # 分类描述
    description = models.TextField("分类描述", blank=True, help_text="分类说明文字，可为空")

    class Meta:
        ordering = ["contest_id", "name"]
        verbose_name = "题目分类"
        verbose_name_plural = "题目分类"
        unique_together = (("contest", "slug"),)

    def __str__(self) -> str:
        return self.name


class Challenge(models.Model):
    """
    题目主体：
    - 关联比赛与分类，记录题面、Flag 信息及分值
    - 支持静态/动态 Flag 与大小写控制
    - 计分模式支持固定/动态衰减，用于排行榜与得分计算
    """

    class Difficulty(models.TextChoices):
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"
        HARD = "hard", "Hard"

    # 所属比赛
    contest = models.ForeignKey(
        "contests.Contest",
        verbose_name="所属比赛",
        related_name="challenges",
        on_delete=models.CASCADE,
        help_text="题目所属的比赛，用于限制可见范围",
    )
    # 分类，可为空
    category = models.ForeignKey(
        ChallengeCategory,
        verbose_name="分类",
        related_name="challenges",
        on_delete=models.SET_NULL,
        null=True,
        help_text="题目分类，便于筛选，可留空",
    )
    # 题目标题
    title = models.CharField("题目标题", max_length=200, help_text="展示给选手的题目名称")
    # 题目标识 slug
    slug = models.SlugField("题目标识", max_length=200, help_text="题目唯一标识，比赛内不可重复")
    # 题目简介
    short_description = models.CharField(
        "题目简介", max_length=255, blank=True, help_text="列表视图展示的简短说明"
    )
    # 题目内容（题面）
    content = models.TextField("题目内容", help_text="完整题面描述，包含背景与要求")
    # 难度枚举
    difficulty = models.CharField(
        "难度",
        max_length=20,
        choices=Difficulty.choices,
        default=Difficulty.MEDIUM,
        help_text="题目难度标签，供选手参考",
    )
    # 基础分值
    base_points = models.PositiveIntegerField("基础分值", default=100, help_text="初始分值，动态模式为起始分")

    class FlagType(models.TextChoices):
        STATIC = "static", "静态 Flag"
        DYNAMIC = "dynamic", "动态 Flag"

    # 标准 Flag（静态或动态前缀）
    flag = models.CharField("Flag", max_length=256, help_text="静态题的 Flag 或动态题的种子")
    # Flag 是否忽略大小写
    flag_case_insensitive = models.BooleanField("忽略大小写", default=True, help_text="判题时是否忽略大小写")
    # Flag 类型：静态/动态
    flag_type = models.CharField(
        "Flag 类型",
        max_length=16,
        choices=FlagType.choices,
        default=FlagType.STATIC,
        help_text="Flag 校验模式，静态或动态",
    )
    # Flag 前缀
    dynamic_prefix = models.CharField(
        "Flag 前缀", max_length=64, blank=True, default="FLAG", help_text="Flag 外层前缀，自动拼接 {flag}"
    )
    # 是否开放作答
    is_active = models.BooleanField("是否开放", default=True, help_text="关闭后题目不会对选手开放")
    # 是否启用靶机
    has_machine = models.BooleanField(
        "启用靶机",
        default=False,
        help_text="开启后需要配置靶机模板；关闭则视为纯题目，不提供靶机实例",
    )

    class ScoringMode(models.TextChoices):
        FIXED = "fixed", "固定分值"
        DYNAMIC = "dynamic", "动态分值"

    class DecayType(models.TextChoices):
        PERCENTAGE = "percentage", "按百分比衰减"
        FIXED_STEP = "fixed_step", "固定分值递减"

    class BloodRewardType(models.TextChoices):
        NONE = "none", "无奖励"
        BONUS = "bonus", "加分奖励"
        NO_DECAY = "no_decay", "前 n 血不衰减"

    # 计分模式：固定/动态衰减
    scoring_mode = models.CharField(
        "计分模式",
        max_length=16,
        choices=ScoringMode.choices,
        default=ScoringMode.FIXED,
        help_text="选择固定分值或动态衰减模式",
    )
    # 衰减类型：百分比或固定扣分
    decay_type = models.CharField(
        "衰减类型",
        max_length=16,
        choices=DecayType.choices,
        default=DecayType.PERCENTAGE,
        help_text="动态计分时的衰减方式",
    )
    # 衰减因子：百分比衰减时为 0-1 浮点；固定扣分时为整数步长
    decay_factor = models.FloatField("衰减因子", default=0.95, help_text="衰减参数，百分比或固定扣分值")
    # 最低分：动态计分时的下限，默认初始分一半
    min_score = models.PositiveIntegerField("最低分", default=50, help_text="动态计分可衰减到的最低得分")
    # n 血奖励类型：无/加分/不衰减
    blood_reward_type = models.CharField(
        "n血奖励类型",
        max_length=16,
        choices=BloodRewardType.choices,
        default=BloodRewardType.NONE,
        help_text="n 血奖励策略，支持无/加分/前 n 血不衰减",
    )
    # n 血数量，决定前几名生效
    blood_reward_count = models.PositiveIntegerField("n血数量", default=0, help_text="享受 n 血奖励的解题名次数")
    # n 血加分列表，仅在奖励类型为加分时使用
    blood_bonus_points = models.JSONField(
        "n血加分列表", default=list, blank=True, help_text="按名次排列的额外加分列表"
    )
    # 出题人
    author = models.ForeignKey(
        User,
        verbose_name="出题人",
        related_name="challenges",
        on_delete=models.SET_NULL,
        null=True,
        help_text="创建题目的管理员/出题人",
    )
    # 创建时间
    created_at = models.DateTimeField("创建时间", auto_now_add=True, help_text="题目创建时间")
    # 更新时间
    updated_at = models.DateTimeField("更新时间", auto_now=True, help_text="题目最近更新时间")

    class Meta:
        unique_together = (("contest", "slug"), ("contest", "title"))
        ordering = ["contest", "slug"]
        verbose_name = "题目"
        verbose_name_plural = "题目"

    def __str__(self) -> str:
        return f"{self.title} ({self.contest.slug})"

    def normalized_flag(self, value: str) -> str:
        """按配置标准化输入 Flag（去空格/大小写），用于统一比对"""
        return value.strip().lower() if self.flag_case_insensitive else value.strip()

    def _assemble_flag(self, prefix: str, body: str) -> str:
        """按约定包装前缀与 flag 主体，并做标准化，生成标准 Flag 串"""
        normalized_prefix = (prefix or "").strip()
        normalized_body = self.normalized_flag(body)
        wrapped = f"{normalized_prefix}{{{normalized_body}}}"
        return self.normalized_flag(wrapped)

    def build_expected_flag(self, user=None, membership=None, secret: str | None = None) -> str:
        """
        构造当前提交者应持有的标准 Flag
        - 静态题目：prefix + {flag}
        - 动态题目：基于 contest/challenge/solver + SECRET_KEY 生成摘要
        """
        if self.flag_type != self.FlagType.DYNAMIC:
            return self._assemble_flag(self.dynamic_prefix, self.flag)

        if membership and getattr(membership, "team", None):
            owner_id = membership.team.id
        else:
            owner_id = getattr(user, "id", None)
        if owner_id is None:
            return self._assemble_flag(self.dynamic_prefix, self.flag)

        flag_secret = secret or get_flag_secret()
        raw = f"{getattr(self, 'contest_id', '')}:{getattr(self, 'id', '')}:{owner_id}:{self.flag}"
        digest = hmac.new(flag_secret.encode("utf-8"), msg=raw.encode("utf-8"), digestmod=hashlib.sha256).hexdigest()[:32]
        return self._assemble_flag(self.dynamic_prefix, digest)

    def check_flag(self, submitted: str, *, user=None, membership=None, secret: str | None = None) -> bool:
        """
        Flag 校验：
        - 静态：直接比对包装后的 flag
        - 动态：基于用户/队伍生成期望值，再比对；若缺少身份则回退旧逻辑
        """
        if self.flag_type == self.FlagType.DYNAMIC and user is None and membership is None:
            # 动态 flag 必须绑定用户或队伍身份，缺失时直接判错以避免被伪造
            return False

        expected = self.build_expected_flag(user=user, membership=membership, secret=secret)
        return self.normalized_flag(submitted) == expected


class ChallengeSolve(models.Model):
    """
    解题记录：
    - 记录选手或队伍的解题得分及时间，用于榜单统计
    """

    # 题目外键
    challenge = models.ForeignKey(
        Challenge,
        verbose_name="题目",
        related_name="solves",
        on_delete=models.CASCADE,
        help_text="对应的题目记录",
    )
    # 解题用户
    user = models.ForeignKey(
        User,
        verbose_name="选手",
        related_name="challenge_solves",
        on_delete=models.CASCADE,
        help_text="解出题目的用户",
    )
    # 解题队伍，可为空（个人赛）
    team = models.ForeignKey(
        "contests.Team",
        verbose_name="队伍",
        related_name="challenge_solves",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="解题所属队伍，个人赛时为空",
    )
    # 最终得分（含动态计分时可能调整）
    awarded_points = models.PositiveIntegerField("得分", default=0, help_text="本次解题获得的最终分值")
    # 额外加分（n 血加分配置产生）
    bonus_points = models.PositiveIntegerField("额外加分", default=0, help_text="n 血奖励产生的额外加分")
    # 解题时间戳
    solved_at = models.DateTimeField("解题时间", default=timezone.now, help_text="解题完成的时间戳")

    class Meta:
        unique_together = ("challenge", "user")
        ordering = ["solved_at"]
        indexes = [
            models.Index(fields=["challenge", "solved_at"]),
            models.Index(fields=["challenge", "team"]),
            models.Index(fields=["challenge", "user"]),
        ]
        verbose_name = "解题记录"
        verbose_name_plural = "解题记录"

    def __str__(self) -> str:
        return f"{self.user} solved {self.challenge}"


class ChallengeTask(models.Model):
    """题目子任务：用于多阶段得分或提示指引"""

    # 关联题目
    challenge = models.ForeignKey(
        Challenge,
        verbose_name="题目",
        related_name="tasks",
        on_delete=models.CASCADE,
        help_text="子任务所属的题目",
    )
    # 子任务标题
    title = models.CharField("子任务标题", max_length=200, help_text="子任务名称，用于提示阶段目标")
    # 子任务描述
    description = models.TextField("子任务描述", blank=True, help_text="子任务的具体说明，可为空")
    # 子任务分值
    points = models.PositiveIntegerField("子任务分值", default=0, help_text="该子任务对应的参考分值")
    # 排序字段
    order = models.PositiveIntegerField("排序", default=1, help_text="展示顺序，越小越靠前")

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "题目子任务"
        verbose_name_plural = "题目子任务"

    def __str__(self) -> str:
        return f"{self.challenge.slug} - {self.title}"


class ChallengeAttachment(models.Model):
    """题目附件：记录可下载的附件链接"""

    # 关联题目
    challenge = models.ForeignKey(
        Challenge,
        verbose_name="题目",
        related_name="attachments",
        on_delete=models.CASCADE,
        help_text="附件关联的题目",
    )
    # 附件名称
    name = models.CharField("附件名称", max_length=200, help_text="附件显示名称")
    # 附件下载链接
    url = models.URLField("附件链接", max_length=500, help_text="附件的下载 URL")
    # 排序字段
    order = models.PositiveIntegerField("排序", default=1, help_text="附件展示顺序")

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "题目附件"
        verbose_name_plural = "题目附件"

    def __str__(self) -> str:
        return f"{self.challenge.slug} - {self.name}"


class ChallengeHint(models.Model):
    """
    题目提示：
    - 支持免费提示与扣分提示
    - order 控制展示顺序
    """

    # 关联题目
    challenge = models.ForeignKey(
        Challenge,
        verbose_name="题目",
        related_name="hints",
        on_delete=models.CASCADE,
        help_text="提示所属的题目",
    )
    # 提示标题
    title = models.CharField("提示标题", max_length=200, help_text="提示显示标题")
    # 提示内容
    content = models.TextField("提示内容", help_text="提示正文内容")
    # 是否免费提示
    is_free = models.BooleanField("是否免费", default=True, help_text="标记提示是否免费可见")
    # 扣分成本（仅在 is_free=False 时有效）
    cost = models.PositiveIntegerField("扣分成本", default=0, help_text="非免费提示的扣分成本")
    # 排序
    order = models.PositiveIntegerField("排序", default=1, help_text="提示展示顺序")
    # 创建时间
    created_at = models.DateTimeField("创建时间", auto_now_add=True, help_text="提示创建时间")
    # 更新时间
    updated_at = models.DateTimeField("更新时间", auto_now=True, help_text="提示最近更新时间")

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "题目提示"
        verbose_name_plural = "题目提示"

    def __str__(self) -> str:
        return f"{self.challenge.slug} - {self.title}"


class ChallengeHintUnlock(models.Model):
    """
    提示解锁记录：
    - 关联用户/队伍，便于后续扣分或审计
    """

    # 提示
    hint = models.ForeignKey(
        ChallengeHint,
        verbose_name="提示",
        related_name="unlocks",
        on_delete=models.CASCADE,
        help_text="被解锁的提示对象",
    )
    # 提示所属题目（冗余便于查询）
    challenge = models.ForeignKey(
        Challenge,
        verbose_name="题目",
        related_name="hint_unlocks",
        on_delete=models.CASCADE,
        help_text="提示所属题目，冗余便于查询",
    )
    # 解锁用户
    user = models.ForeignKey(
        User,
        verbose_name="用户",
        related_name="hint_unlocks",
        on_delete=models.CASCADE,
        help_text="发起解锁的用户",
    )
    # 解锁队伍，可为空（个人赛）
    team = models.ForeignKey(
        "contests.Team",
        verbose_name="队伍",
        related_name="hint_unlocks",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="组队赛的所属队伍，个人赛留空",
    )
    # 解锁成本（扣分值），与提示 cost 一致
    cost = models.PositiveIntegerField("扣分成本", default=0, help_text="本次解锁消耗的积分")
    # 解锁时间
    unlocked_at = models.DateTimeField("解锁时间", auto_now_add=True, help_text="提示被解锁的时间")

    class Meta:
        unique_together = ("hint", "user")
        ordering = ["-unlocked_at"]
        indexes = [
            models.Index(fields=["challenge", "team"]),
            models.Index(fields=["challenge", "user"]),
        ]
        verbose_name = "提示解锁"
        verbose_name_plural = "提示解锁"

    def __str__(self) -> str:
        return f"{self.user} unlocked {self.hint}"
