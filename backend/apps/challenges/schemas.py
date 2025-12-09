# apps/challenges/schemas.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar, Optional, List, Dict

from apps.common.base.base_schema import BaseSchema
from apps.common.exceptions import ValidationError
from apps.common.utils.validators import validate_slug, forbid_dangerous_html


# Schema 层：定义题目创建/更新/提交/提示/附件上传的入参结构与校验逻辑，确保视图/服务收到的参数符合业务规则


@dataclass
class ChallengeCreateSchema(BaseSchema[None]):
    """
    创建题目入参：
    - 覆盖题目信息、Flag、分类、子任务、附件与提示
    - 自动校验必填字段、分值与子任务/附件合法性
    """
    auto_validate: ClassVar[bool] = True
    # 比赛标识
    contest_slug: str
    # 题目标题
    title: str
    # 题目标识
    slug: str
    # 题目内容
    content: str
    # 分类名，可选
    category: Optional[str] = None
    # 简介
    short_description: str = ""
    # 难度
    difficulty: str = "medium"
    # 基础分值
    base_points: int = 100
    # Flag 类型：static/dynamic（静态/动态均可搭配前缀）
    flag_type: str = "static"
    # 标准 Flag（静态题必填；动态题用作种子，不含花括号）
    flag: str = ""
    # Flag 前缀（可选，最终 flag=前缀 + '{' + flag + '}'，静态/动态均可用）
    dynamic_prefix: str = ""
    # 是否忽略大小写
    flag_case_insensitive: bool = True
    # 是否启用靶机
    has_machine: bool = False
    # 子任务列表
    tasks: List[Dict] = field(default_factory=list)
    # 附件列表
    attachments: List[Dict] = field(default_factory=list)
    # 提示列表
    hints: List[Dict] = field(default_factory=list)
    # 计分模式：fixed/dynamic
    scoring_mode: str = "fixed"
    # 衰减类型：percentage/fixed_step
    decay_type: str = "percentage"
    # 衰减因子：百分比 <1，固定扣分>0
    decay_factor: float = 0.95
    # 最低分：默认初始分一半，需小于 base_points
    min_score: Optional[int] = None
    # n 血奖励类型：none/bonus/no_decay
    blood_reward_type: str = "none"
    # n 血数量
    blood_reward_count: int = 0
    # n 血加分列表（按名次排序）
    blood_bonus_points: List[int] = field(default_factory=list)

    def validate(self) -> None:
        """校验题目必填字段、分值、子任务与附件，确保创建请求符合业务约束"""
        if not self.title:
            raise ValidationError(message="题目标题不能为空")
        forbid_dangerous_html(self.title, field_name="题目标题")
        if not self.slug:
            raise ValidationError(message="题目标识不能为空")
        else:
            validate_slug(self.slug)
        if not self.content:
            raise ValidationError(message="题目内容不能为空")
        forbid_dangerous_html(self.content, field_name="题目内容")
        if self.short_description:
            forbid_dangerous_html(self.short_description, field_name="题目简介")
        if self.base_points <= 0:
            raise ValidationError(message="分值必须大于 0")
        if self.flag_type not in {"static", "dynamic"}:
            raise ValidationError(message="提交类型无效，请选择静态或动态")
        if not self.flag:
            if self.flag_type == "static":
                raise ValidationError(message="静态题的答案不能为空")
            else:
                raise ValidationError(message="动态题的种子不能为空")
        if self.has_machine is not None:
            self.has_machine = bool(self.has_machine)
        if any(ch in (self.dynamic_prefix or "") for ch in ["{", "}"]):
            raise ValidationError(message="前缀无需包含花括号，系统会自动拼接为 前缀{flag}")
        for task in self.tasks:
            if not task.get("title"):
                raise ValidationError(message="子任务标题不能为空")
            if int(task.get("points", 0)) < 0:
                raise ValidationError(message="子任务分值不能为负数")
        for attach in self.attachments:
            if not attach.get("name") or not attach.get("url"):
                raise ValidationError(message="附件名称和链接均不能为空")
            forbid_dangerous_html(str(attach.get("name", "")), field_name="附件名称")
        for hint in self.hints:
            if not hint.get("title"):
                raise ValidationError(message="提示标题不能为空")
            cost_val = int(hint.get("cost", 0))
            if cost_val < 0:
                raise ValidationError(message="提示扣分必须大于等于 0")
            forbid_dangerous_html(str(hint.get("title", "")), field_name="提示标题")
            forbid_dangerous_html(str(hint.get("content", "")), field_name="提示内容")
        if self.scoring_mode not in {"fixed", "dynamic"}:
            raise ValidationError(message="计分模式不正确")
        if self.decay_type not in {"percentage", "fixed_step"}:
            raise ValidationError(message="衰减类型不正确")
        if self.decay_type == "percentage":
            if not (0 < float(self.decay_factor) < 1):
                raise ValidationError(message="百分比衰减因子需在 0-1 之间")
        else:
            if float(self.decay_factor) <= 0:
                raise ValidationError(message="固定扣分必须大于 0")
        # 最低分默认半分
        if self.min_score is None:
            self.min_score = max(1, self.base_points // 2)
        if self.min_score <= 0 or self.min_score >= self.base_points:
            raise ValidationError(message="最低分需大于 0 且小于初始分值")
        # n 血奖励校验
        if self.blood_reward_type not in {"none", "bonus", "no_decay"}:
            raise ValidationError(message="n血奖励类型不正确")
        self.blood_reward_count = int(self.blood_reward_count or 0)
        if self.blood_reward_type == "none":
            self.blood_reward_count = 0
            self.blood_bonus_points = []
        elif self.blood_reward_count <= 0:
            raise ValidationError(message="请填写 n 血数量")
        elif self.blood_reward_type == "bonus":
            cleaned_bonus: list[int] = []
            for idx in range(self.blood_reward_count):
                try:
                    bonus_val = int(self.blood_bonus_points[idx])
                except Exception:
                    raise ValidationError(message=f"请填写第 {idx + 1} 血的加分")
                if bonus_val < 0:
                    raise ValidationError(message="加分需大于等于 0")
                cleaned_bonus.append(bonus_val)
            self.blood_bonus_points = cleaned_bonus
        else:
            if self.scoring_mode != "dynamic":
                raise ValidationError(message="仅动态分值支持前 n 血不衰减")
            self.blood_bonus_points = []


@dataclass
class ChallengeUpdateSchema(ChallengeCreateSchema):
    """更新题目入参：沿用创建校验逻辑"""
    auto_validate: ClassVar[bool] = True
    has_machine: Optional[bool] = None


@dataclass
class ChallengeSubmitSchema(BaseSchema[None]):
    """提交 Flag 入参：仅包含 Flag"""
    auto_validate: ClassVar[bool] = True
    # 提交的 Flag
    flag: str

    def validate(self) -> None:
        """校验 Flag 非空"""
        if not self.flag:
            raise ValidationError(message="请输入 Flag")


@dataclass
class HintUnlockSchema(BaseSchema[None]):
    """解锁提示入参：无额外字段，预留扩展"""
    auto_validate: ClassVar[bool] = True

    def validate(self) -> None:
        """当前无额外字段，预留扩展占位"""
        return None


@dataclass
class AttachmentUploadSchema(BaseSchema[None]):
    """附件上传入参：支持可选比赛/题目标识用于归档路径"""
    auto_validate: ClassVar[bool] = True
    # 可选：归档到具体比赛
    contest_slug: Optional[str] = None
    # 可选：归档到具体题目
    challenge_slug: Optional[str] = None
    # 上传的原始文件名
    filename: str = ""

    def validate(self) -> None:
        if self.contest_slug:
            validate_slug(self.contest_slug)
        if self.challenge_slug:
            validate_slug(self.challenge_slug)
        if not self.filename:
            raise ValidationError(message="请提供文件名")
