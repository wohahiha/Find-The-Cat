from __future__ import annotations

from apps.common.base.base_service import BaseService

# 服务骨架：预留靶机启动/停止、动态 flag 注入等逻辑。


class PlaceholderMachineService(BaseService[None]):
    """
    占位服务：
    - 后续实现容器管理、端口分配、动态 Flag 注入等流程。
    """

    atomic_enabled = False

    def perform(self, *args, **kwargs):
        raise NotImplementedError("Machines 模块尚未实现")
