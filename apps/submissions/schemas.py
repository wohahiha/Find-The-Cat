from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from apps.common.base.base_schema import BaseSchema
from apps.common.exceptions import ValidationError


# Schema：定义提交 Flag 的入参与校验


@dataclass
class SubmissionCreateSchema(BaseSchema[None]):
    """
    提交 Flag 入参：
    - 需要比赛/题目标识与提交的 Flag
    """

    auto_validate: ClassVar[bool] = True
    contest_slug: str
    challenge_slug: str
    flag: str

    def validate(self) -> None:
        """校验比赛/题目/Flag 必填"""
        if not self.contest_slug:
            raise ValidationError(message="缺少比赛标识")
        if not self.challenge_slug:
            raise ValidationError(message="缺少题目标识")
        if not self.flag:
            raise ValidationError(message="请填写提交内容（Flag）")
        if len(self.flag) > 1024:
            raise ValidationError(message="提交内容过长，请控制在 1024 字以内")
