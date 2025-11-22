# apps/common/base/base_service.py

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from django.db import transaction

from apps.common.exceptions import BizError

ServiceReturn = TypeVar("ServiceReturn")


class BaseService(ABC, Generic[ServiceReturn]):
    """
    Service 层业务逻辑基类。

    约束：
        - 负责编排业务逻辑，不直接处理 HTTP。
        - 使用普通 Python 参数，避免依赖 request。
        - 通过仓储/Repo 访问持久化层，避免散乱 ORM 调用。
        - 默认在事务中执行 `perform`。
        - 任何业务失败都转换为 BizError。

    标准流程：validate(...) -> perform(...) -> handle_error(...)
    """

    atomic_enabled: bool = True
    atomic_savepoint: bool = True

    # ------------------------
    # 工具方法
    # ------------------------

    @staticmethod
    def atomic(*args, **kwargs):
        """
        为子类提供 `transaction.atomic` 上下文管理器。

            @BaseService.atomic()
            def do_something(...):
                ...
        """
        return transaction.atomic(*args, **kwargs)

    # ------------------------
    # 子类扩展点
    # ------------------------

    def validate(self, *args, **kwargs) -> None:
        """
        可选的业务预检查钩子（权限、状态等），默认空实现。
        """
        return None

    @abstractmethod
    def perform(self, *args, **kwargs) -> ServiceReturn:
        """
        子类必须实现的业务核心逻辑。
        """

    def execute(self, *args, **kwargs) -> ServiceReturn:
        """
        Service 对外的统一入口，封装标准流程。
        """
        try:
            self.validate(*args, **kwargs)
            if self.atomic_enabled:
                with self.atomic(savepoint=self.atomic_savepoint):
                    return self.perform(*args, **kwargs)
            return self.perform(*args, **kwargs)
        except Exception as exc:
            return self.handle_error(exc)

    __call__ = execute

    def handle_error(self, exc: Exception) -> ServiceReturn:
        """
        将所有非 BizError 的异常转换为 BizError，确保对外失败契约一致。
        """
        if isinstance(exc, BizError):
            raise exc
        raise BizError(message=str(exc)) from exc
