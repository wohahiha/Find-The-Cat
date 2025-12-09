from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from apps.common.base.base_schema import BaseSchema
from apps.common.exceptions import ValidationError


# Schema：靶机启动与关闭的入参校验


@dataclass
class MachineStartSchema(BaseSchema[None]):
    """
    启动靶机入参：
    - 需要比赛/题目标识
    """
    auto_validate: ClassVar[bool] = True
    contest_slug: str
    challenge_slug: str

    def validate(self) -> None:
        """校验比赛与题目标识必填"""
        if not self.contest_slug:
            raise ValidationError(message="缺少比赛标识")
        if not self.challenge_slug:
            raise ValidationError(message="缺少题目标识")


@dataclass
class MachineStopSchema(BaseSchema[None]):
    """
    停止靶机入参：
    - 通过实例 ID 指定
    """
    auto_validate: ClassVar[bool] = True
    machine_id: int

    def validate(self) -> None:
        """校验实例 ID 合法"""
        if self.machine_id <= 0:
            raise ValidationError(message="非法的实例 ID")


@dataclass
class MachineExtendSchema(BaseSchema[None]):
    """
    延长靶机时长入参：
    - 通过实例 ID 指定
    - 可选指定延长分钟数，未传使用默认值
    """
    auto_validate: ClassVar[bool] = True
    machine_id: int
    minutes: int | None = None

    def validate(self) -> None:
        if self.machine_id <= 0:
            raise ValidationError(message="非法的实例 ID")
        if self.minutes is not None and self.minutes <= 0:
            raise ValidationError(message="延长时间必须大于 0")
