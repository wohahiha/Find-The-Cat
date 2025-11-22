from __future__ import annotations

from django.db import models

# 模型骨架：
# - 后续将定义 MachineInstance 等模型，记录靶机容器、端口、状态、动态 flag。
# - 当前占位，避免生成实际表结构，待设计完成后补充字段与约束。


class PlaceholderMachine(models.Model):
    """
    占位模型：
    - 仅提示后续需要实现靶机实例模型。
    """

    class Meta:
        managed = False  # 不生成数据库表
        verbose_name = "占位-靶机实例"
        verbose_name_plural = "占位-靶机实例"
