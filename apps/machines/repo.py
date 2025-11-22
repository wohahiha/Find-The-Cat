from __future__ import annotations

from apps.common.base.base_repo import BaseRepo
from apps.common.exceptions import NotFoundError

from .models import MachineInstance

# 仓储层：封装靶机实例的查询与持久化。


class MachineRepo(BaseRepo[MachineInstance]):
    """靶机实例仓储：提供按主键获取与活跃查询。"""

    model = MachineInstance

    def get_by_id(self, pk: int) -> MachineInstance:
        try:
            return self.filter(pk=pk).get()
        except MachineInstance.DoesNotExist as exc:  # type: ignore[attr-defined]
            raise NotFoundError(message="靶机实例不存在") from exc
