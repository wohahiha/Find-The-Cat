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

    def running_for_user(self, *, contest, challenge, user) -> MachineInstance | None:
        """查询用户在指定题目下的运行中实例。"""
        return (
            self.filter(
                contest=contest,
                challenge=challenge,
                user=user,
                status=MachineInstance.Status.RUNNING,
            )
            .order_by("-created_at")
            .first()
        )

    def running_ports(self) -> set[int]:
        """获取所有运行中实例占用的端口集合，用于分配去重。"""
        return set(
            p
            for p in self.filter(status=MachineInstance.Status.RUNNING)
            .exclude(port=None)
            .values_list("port", flat=True)
        )
