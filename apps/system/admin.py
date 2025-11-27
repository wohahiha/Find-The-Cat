from __future__ import annotations

from django.contrib import admin
from django import forms

from apps.common.infra.logger import get_logger, logger_extra
from .services import ConfigService
from .models import SystemConfig

logger = get_logger(__name__)
config_service = ConfigService()


@admin.register(SystemConfig)
class SystemConfigAdmin(admin.ModelAdmin):
    """
    系统配置后台管理：
    - 支持在运行期为配置键设定覆盖值
    - 核心键需谨慎操作，建议超级管理员管理
    """

    list_display = ("key", "description", "value_type", "current_value", "is_required", "is_sensitive", "updated_at")
    list_filter = ("value_type", "is_required", "is_sensitive")
    search_fields = ("key", "description")
    ordering = ("key",)
    readonly_fields = ("key", "description", "detail_description", "value_type", "is_sensitive", "is_required")

    class SystemConfigAdminForm(forms.ModelForm):
        """根据值类型切换表单控件并做类型校验"""

        class Meta:
            model = SystemConfig
            fields = (
                "key",
                "value",
                "value_type",
                "is_sensitive",
                "is_required",
                "description",
                "detail_description",
            )

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            cfg = self.instance

            # 切换字段类型与初始值
            if cfg.value_type == SystemConfig.ValueType.INT:
                self.fields["value"] = forms.IntegerField(
                    label="配置值",
                    required=cfg.is_required,
                    initial=cfg.cast_value(),
                    help_text="",
                )
            elif cfg.value_type == SystemConfig.ValueType.BOOL:
                self.fields["value"] = forms.BooleanField(
                    label="配置值",
                    required=False,
                    initial=bool(cfg.cast_value()),
                    help_text="",
                )
            elif cfg.value_type == SystemConfig.ValueType.JSON:
                self.fields["value"] = forms.JSONField(
                    label="配置值",
                    required=cfg.is_required,
                    initial=cfg.cast_value(),
                    help_text="",
                )
            else:
                widget = forms.PasswordInput(render_value=True) if cfg.is_sensitive else forms.TextInput()
                self.fields["value"] = forms.CharField(
                    label="配置值",
                    required=cfg.is_required,
                    initial=cfg.cast_value(),
                    widget=widget,
                    help_text="",
                )

            # 只读字段保持禁用，防止误改元信息
            for name in (
                "key",
                "value_type",
                "is_sensitive",
                "is_required",
                "description",
                "detail_description",
            ):
                if name in self.fields and name != "value":
                    self.fields[name].disabled = True

        def clean_value(self):
            """按类型校验并转为字符串存储"""
            cfg = self.instance
            val = self.cleaned_data.get("value")
            if cfg.value_type == SystemConfig.ValueType.INT and not isinstance(val, int):
                raise forms.ValidationError("请输入整数")
            if cfg.value_type == SystemConfig.ValueType.BOOL:
                val = bool(val)
            if cfg.value_type == SystemConfig.ValueType.JSON and val is None and cfg.is_required:
                raise forms.ValidationError("必填项不能为空")
            if cfg.is_required and val in (None, ""):
                raise forms.ValidationError("必填项不能为空")
            return val

        def save(self, commit=True):
            cfg = super().save(commit=False)
            val = self.cleaned_data.get("value")
            # 持久化为字符串
            if cfg.value_type == SystemConfig.ValueType.JSON:
                cfg.value = self.fields["value"].widget.value_from_datadict(
                    {"value": val}, {}, "value"
                )
            else:
                cfg.value = str(val) if val is not None else ""
            if commit:
                cfg.save()
            return cfg

    form = SystemConfigAdminForm


    def save_model(self, request, obj: SystemConfig, form, change):
        """保存时记录日志，提示仅覆盖运行期配置"""
        super().save_model(request, obj, form, change)
        config_service.invalidate(obj.key)
        logger.info(
            "更新系统配置",
            extra=logger_extra(
                {"admin": getattr(request.user, "username", None), "key": obj.key}
            ),
        )

    @admin.display(description="值预览")
    def current_value(self, obj: SystemConfig) -> str:
        """
        当前生效值：
        - 若后台启用则取配置值
        - 否则回退到 settings/.env
        - 敏感字段脱敏
        """
        effective = config_service.get(obj.key, "")
        if obj.is_sensitive and effective not in (None, ""):
            return "******"
        return "" if effective is None else str(effective)

    def has_add_permission(self, request):
        """禁止新增，统一由预置配置生成"""
        return False

    def has_delete_permission(self, request, obj=None):
        """禁止删除配置项"""
        return False

    def get_queryset(self, request):
        """进入后台前确保预置配置存在"""
        config_service.ensure_supported_configs()
        qs = super().get_queryset(request)
        return qs.filter(key__in=config_service.SUPPORTED_CONFIGS.keys())
