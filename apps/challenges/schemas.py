# apps/challenges/schemas.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar, Optional, List, Dict

from apps.common.base.base_schema import BaseSchema
from apps.common.exceptions import ValidationError

# Schema 层：定义题目创建/更新/提交的入参结构与校验逻辑。


@dataclass
class ChallengeCreateSchema(BaseSchema[None]):
    """
    创建题目入参：
    - 覆盖题目信息、Flag、分类、子任务与附件。
    - 自动校验必填字段、分值与子任务/附件合法性。
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
    # 标准 Flag
    flag: str = ""
    # 是否忽略大小写
    flag_case_insensitive: bool = True
    # Flag 类型：static/dynamic
    flag_type: str = "static"
    # 动态 Flag 前缀
    dynamic_prefix: str = ""
    # 子任务列表
    tasks: List[Dict] = field(default_factory=list)
    # 附件列表
    attachments: List[Dict] = field(default_factory=list)

    def validate(self) -> None:
        """校验题目必填字段、分值、子任务与附件。"""
        if not self.title:
            raise ValidationError(message="题目标题不能为空")
        if not self.slug:
            raise ValidationError(message="题目标识不能为空")
        if not self.content:
            raise ValidationError(message="题目内容不能为空")
        if not self.flag:
            raise ValidationError(message="必须设置 Flag")
        if self.base_points <= 0:
            raise ValidationError(message="分值必须大于 0")
        if self.flag_type not in {"static", "dynamic"}:
            raise ValidationError(message="Flag 类型不正确")
        for task in self.tasks:
            if not task.get("title"):
                raise ValidationError(message="子任务标题不能为空")
            if int(task.get("points", 0)) < 0:
                raise ValidationError(message="子任务分值不能为负数")
        for attach in self.attachments:
            if not attach.get("name") or not attach.get("url"):
                raise ValidationError(message="附件名称和链接均不能为空")


@dataclass
class ChallengeUpdateSchema(ChallengeCreateSchema):
    """更新题目入参：沿用创建校验逻辑。"""
    auto_validate: ClassVar[bool] = True


@dataclass
class ChallengeSubmitSchema(BaseSchema[None]):
    """提交 Flag 入参：仅包含 Flag。"""
    auto_validate: ClassVar[bool] = True
    # 提交的 Flag
    flag: str

    def validate(self) -> None:
        """校验 Flag 非空。"""
        if not self.flag:
            raise ValidationError(message="请输入 Flag")
