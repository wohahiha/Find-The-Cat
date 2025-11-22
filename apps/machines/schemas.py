from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from apps.common.base.base_schema import BaseSchema

# Schema 骨架：后续定义启动/停止靶机、动态 Flag 等入参。


@dataclass
class PlaceholderMachineSchema(BaseSchema[None]):
    """
    占位 Schema：
    - 待补充靶机操作的参数校验。
    """
    auto_validate: ClassVar[bool] = False
