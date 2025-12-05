from __future__ import annotations

from typing import Any

from apps.common.base.base_repo import BaseRepo
from .models import SystemConfig


class SystemConfigRepo(BaseRepo[SystemConfig]):
    """系统配置仓储：封装配置的读取与过滤"""

    model = SystemConfig

    def get_by_key(self, key: str) -> SystemConfig | None:
        """根据 key 获取配置"""
        return self.model.objects.filter(key=key).first()

    def get_map(self) -> dict[str, Any]:
        """获取所有配置的键值映射"""
        result: dict[str, Any] = {}
        for cfg in self.model.objects.all():
            result[cfg.key] = cfg.cast_value()
        return result
