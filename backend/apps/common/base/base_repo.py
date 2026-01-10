# apps/common/base/base_repo.py

from __future__ import annotations

from abc import ABC
from typing import Any, Generic, Iterable, Optional, TypeVar

from django.db.models import Model, QuerySet

T = TypeVar("T", bound=Model)


class BaseRepo(ABC, Generic[T]):
    """
    Repository（数据访问层）基类：
    - 业务目标：统一封装 Django ORM 读写细节，给 Service 提供稳定接口
    - 模块角色：集中管理 select_related/prefetch/filter 等查询配置，减少各模块重复 CRUD
    - 用法示例：class UserRepo(BaseRepo[User]): model = User
    """

    #: 子类必须指定对应的模型
    model: type[T]

    # ------------------------
    # QuerySet 构建
    # ------------------------

    def get_queryset(self) -> QuerySet[T]:
        """
        返回默认 QuerySet子类可覆盖以附加 select_related/prefetch/filter
        """
        if not getattr(self, "model", None):
            raise NotImplementedError("BaseRepo 子类必须声明 model 属性")
        return self.model._default_manager.all()

    def filter(self, *, queryset: Optional[QuerySet[T]] = None, **filters) -> QuerySet[T]:
        """
        通用过滤入口，允许注入自定义 QuerySet
        """
        qs = queryset or self.get_queryset()
        return qs.filter(**filters)

    def list(self, **filters) -> Iterable[T]:
        """
        返回满足条件的对象列表默认直接使用 filter
        """
        return self.filter(**filters)

    def get_by_id(self, pk: Any, *, queryset: Optional[QuerySet[T]] = None) -> T:
        """
        根据主键获取对象，不存在时让上层自行捕获 DoesNotExist 转 BizError
        """
        qs = queryset or self.get_queryset()
        return qs.get(pk=pk)

    def get_or_none(self, *, queryset: Optional[QuerySet[T]] = None, **filters) -> Optional[T]:
        """
        返回符合条件的单个对象，未命中则为 None
        """
        qs = queryset or self.get_queryset()
        return qs.filter(**filters).first()

    def exists(self, **filters) -> bool:
        """
        判断是否存在满足条件的记录
        """
        return self.filter(**filters).exists()

    def count(self, **filters) -> int:
        """
        返回满足条件的记录数
        """
        return self.filter(**filters).count()

    # ------------------------
    # 写操作（可在子类中覆写以扩展审计/软删等需求）
    # ------------------------

    def create(self, data: dict) -> T:
        """
        创建记录；若需写入额外字段，可在子类中统一处理
        """
        return self.model._default_manager.create(**data)

    def update(self, instance: T, data: dict) -> T:
        """
        批量更新字段并保存，返回最新实例
        """
        for field, value in data.items():
            setattr(instance, field, value)
        if data:
            instance.save(update_fields=list(data.keys()))
        else:
            instance.save()
        return instance

    def delete(self, instance: T) -> None:
        """
        默认调用硬删除；如需软删可在子类覆写为标记字段
        """
        instance.delete()

    # 子类可在此基础上扩展 bulk_create / bulk_update / select_for_update 等高阶操作
