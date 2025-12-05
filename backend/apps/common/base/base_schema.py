# apps/common/base/base_schema.py

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, fields
from typing import Any, ClassVar, Dict, Generic, Iterable, Mapping, Optional, TypeVar

T = TypeVar("T")
SchemaType = TypeVar("SchemaType", bound="BaseSchema[Any]")


@dataclass
class BaseSchema(ABC, Generic[T]):
    """
    业务 Schema / DTO 基类

    目的：
        - 用于 Service 层在 Model 与外部输入之间传递结构化数据；
        - 聚合字段校验逻辑，替代零散的 serializer/表单校验；
        - 提供通用的字典化、Model 映射与回写能力

    子类示例：
        @dataclass
        class UserCreateSchema(BaseSchema):
            username: str
            password: str

            def validate(self):
                if len(self.username) < 3:
                    raise BizError("用户名过短")
    """

    #: 是否在 __post_init__ 中自动执行 validate
    auto_validate: ClassVar[bool] = False
    #: 字段别名映射：用于兼容不同命名风格（如中文拼音）到内部字段
    ALIASES: ClassVar[dict[str, str]] = {}

    def __post_init__(self):
        if self.auto_validate:
            self.validate()

    # ------------------------
    # 校验钩子
    # ------------------------

    @abstractmethod
    def validate(self) -> None:
        """
        子类实现字段/业务约束校验，出错时抛 BizError
        """

    # ------------------------
    # 数据转换与同步
    # ------------------------

    def to_dict(
            self,
            *,
            exclude_none: bool = False,
            exclude: Iterable[str] | None = None,
    ) -> Dict[str, Any]:
        """
        将 Schema 转为 dict，支持过滤 None 或移除指定字段
        """
        data = asdict(self)
        if exclude_none:
            data = {key: value for key, value in data.items() if value is not None}
        if exclude:
            for key in exclude:
                data.pop(key, None)
        return data

    def to_model_kwargs(
            self,
            *,
            exclude_none: bool = True,
            mapping: Mapping[str, str] | None = None,
    ) -> Dict[str, Any]:
        """
        根据 mapping 将 Schema 字段名映射到 Model 字段，便于 create/update
        """
        data = self.to_dict(exclude_none=exclude_none)
        if not mapping:
            return data
        return {mapping.get(key, key): value for key, value in data.items()}

    def apply_to_model(
            self,
            instance: T,
            *,
            fields: Iterable[str] | None = None,
            save: bool = False,
            exclude_none: bool = True,
    ) -> T:
        """
        将 Schema 字段写回已有 Model 实例，可选保存
        """
        update_data = self.to_dict(exclude_none=exclude_none)
        if fields:
            update_data = {field: update_data[field] for field in fields if field in update_data}
        for key, value in update_data.items():
            setattr(instance, key, value)
        if save:
            if update_data:
                instance.save(update_fields=list(update_data.keys()))
            else:
                instance.save()
        return instance

    # ------------------------
    # 构建方法
    # ------------------------

    @classmethod
    def from_dict(
            cls: type[SchemaType],
            data: Dict[str, Any],
            *,
            auto_validate: Optional[bool] = None,
    ) -> SchemaType:
        """
        将外部 payload 转为 Schema；auto_validate 控制是否立即校验
        """
        # 兼容 QueryDict/类似 Mapping，统一转为普通 dict
        if not isinstance(data, dict):
            data = dict(data)
        # 兼容别名：将外部使用的别名（如中文拼音）映射到内部字段名
        if cls.ALIASES:
            normalized = dict(data)
            for alias, target in cls.ALIASES.items():
                if alias in normalized and target not in normalized:
                    normalized[target] = normalized.pop(alias)
                elif alias in normalized:
                    # 已存在目标字段时，移除别名避免 __init__ 收到未知参数
                    normalized.pop(alias)
            data = normalized
        instance = cls(**data)  # type: ignore[arg-type]
        if auto_validate or (auto_validate is None and cls.auto_validate):
            instance.validate()
        return instance

    @classmethod
    def from_model(
            cls: type[SchemaType],
            model: T,
            *,
            field_map: Mapping[str, str] | None = None,
            extra: Dict[str, Any] | None = None,
    ) -> SchemaType:
        """
        将 Model 实例转换为 Schema，可通过 field_map 指定属性映射
        """
        payload: Dict[str, Any] = {}
        attr_map = field_map or {}
        for field in fields(cls):
            target_attr = attr_map.get(field.name, field.name)
            if hasattr(model, target_attr):
                payload[field.name] = getattr(model, target_attr)
        if extra:
            payload.update(extra)
        return cls(**payload)
