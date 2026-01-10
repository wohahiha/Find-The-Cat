# -*- coding: utf-8 -*-
"""
认证与权限 Schema 定义

用于后续 RBAC、OAuth2 等流程的参数校验占位。
"""

from dataclasses import dataclass
from typing import List, Optional

from apps.common.base.base_schema import BaseSchema
from apps.common.exceptions import ValidationError


@dataclass
class RoleSchema(BaseSchema["RoleSchema"]):
    """
    角色数据结构
    """

    name: str
    description: Optional[str] = None
    permissions: Optional[List[str]] = None

    def validate(self) -> None:
        """
        基础校验：确保角色名非空
        """
        if not self.name:
            raise ValidationError("角色名称不能为空")


@dataclass
class PermissionSchema(BaseSchema["PermissionSchema"]):
    """
    权限数据结构
    """

    code: str
    name: str
    description: Optional[str] = None

    def validate(self) -> None:
        """
        基础校验：确保权限编码与名称非空
        """
        if not self.code or not self.name:
            raise ValidationError("权限编码与名称不能为空")
