from __future__ import annotations

import json
from typing import Any

from django.db import models


class SystemConfig(models.Model):
    """
    系统配置项模型
    - 场景：允许管理员在后台为可覆盖的系统参数设置运行期值，优先于 .env/settings
    - 约束：仅存储可运行期覆盖的业务参数，启动依赖仍需 .env 提供
    """

    class ValueType(models.TextChoices):
        STRING = "string", "字符串"
        INT = "int", "整数"
        BOOL = "bool", "布尔"
        JSON = "json", "JSON"
        SECRET = "secret", "字符串"

    key = models.CharField("键", max_length=120, unique=True, db_index=True)
    value = models.TextField("配置值")
    value_type = models.CharField(
        "值类型", max_length=20, choices=ValueType.choices, default=ValueType.STRING
    )
    description = models.TextField("说明", blank=True)
    detail_description = models.TextField("详细用途说明", blank=True, default="")
    is_sensitive = models.BooleanField(
        "敏感字段",
        default=False,
        help_text="后台仅展示脱敏值 ' *** '",
    )
    is_required = models.BooleanField(
        "必填",
        default=False,
        help_text="此配置为必填项，缺失可能导致平台不可用",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "SYSTEM"
        verbose_name_plural = "基础配置"
        ordering = ["key"]

    def __str__(self) -> str:
        """后台对象显示使用键名，便于识别"""
        return self.key

    def cast_value(self) -> Any:
        """根据类型转换配置值"""
        if self.value_type == self.ValueType.INT:
            try:
                return int(self.value)
            except (TypeError, ValueError):
                return self.value
        if self.value_type == self.ValueType.BOOL:
            return str(self.value).strip().lower() in {"1", "true", "yes", "on"}
        if self.value_type == self.ValueType.JSON:
            try:
                return json.loads(self.value)
            except json.JSONDecodeError:
                return self.value
        # SECRET / STRING 默认返回原值
        return self.value

    @property
    def display_value(self) -> str:
        """后台展示值：敏感字段脱敏处理"""
        if self.is_sensitive and self.value:
            return "******"
        return str(self.value)
