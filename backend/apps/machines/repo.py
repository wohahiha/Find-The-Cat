from __future__ import annotations

from django.db import models
from django.db.models import QuerySet

from apps.common.base.base_repo import BaseRepo
from apps.common.exceptions import NotFoundError

from .models import MachineInstance


# 仓储层：封装靶机实例的查询与持久化


class MachineRepo(BaseRepo[MachineInstance]):
    """靶机实例仓储：提供按主键获取与活跃查询"""

    model = MachineInstance

    def get_by_id(self, pk: int, *, queryset: QuerySet[MachineInstance] | None = None) -> MachineInstance:
        """依据主键获取实例，未找到抛业务级 404"""
        # 供停止/详情场景使用，避免直接操作 ORM 抛出默认异常
        try:
            qs = queryset or self.filter(pk=pk)
            return qs.select_related("contest", "challenge", "user", "team").get()
        except MachineInstance.DoesNotExist as exc:  # type: ignore[attr-defined]
            raise NotFoundError(message="靶机实例不存在") from exc

    def running_for_user(self, *, contest, challenge, user) -> MachineInstance | None:
        """查询用户在指定题目下的运行中实例"""
        # 防止同一用户在同一题目下重复启动靶机
        return (
            self.filter(
                contest=contest,
                challenge=challenge,
                user=user,
                status=MachineInstance.Status.RUNNING,
            )
            .select_related("contest", "challenge", "user", "team")
            .order_by("-created_at")
            .first()
        )

    def running_ports(self) -> set[int]:
        """获取所有运行中实例占用的端口集合，用于分配去重"""
        # 结合数据库层数据，避免端口冲突
        return set(
            p
            for p in self.filter(status=MachineInstance.Status.RUNNING)
            .exclude(port=None)
            .values_list("port", flat=True)
        )

    def running_before(self, cutoff_time):
        """获取超过指定时间仍在运行的实例 QuerySet（优先使用 expires_at）"""
        qs = self.filter(status=MachineInstance.Status.RUNNING)
        # 优先 expires_at，兼容历史数据回退 created_at
        return qs.filter(
            models.Q(expires_at__lt=cutoff_time) | models.Q(expires_at__isnull=True, created_at__lt=cutoff_time)
        )

    @staticmethod
    def mark_stopped(instance: MachineInstance, *, clear_port: bool = True) -> MachineInstance:
        """
        标记实例为已停止，必要时清理端口与容器 ID
        """
        instance.status = MachineInstance.Status.STOPPED
        if clear_port:
            instance.port = None
        instance.container_id = ""
        instance.save(update_fields=["status", "port", "container_id", "updated_at"])
        return instance
