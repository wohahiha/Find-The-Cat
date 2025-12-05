# -*- coding: utf-8 -*-
"""
认证与权限业务逻辑层

后续将承载：
- 角色/权限的增删改查
- 轻量级 RBAC 判定
- OAuth2 / 单点登录等认证扩展
"""

from apps.common.base.base_service import BaseService


class RBACService(BaseService):
    """
    RBAC 业务服务
    """

    # TODO: 待需求明确后补充具体逻辑
    def perform(self, *args, **kwargs):  # type: ignore[override]
        """
        基础占位方法，防止抽象类报错
        """
        return None
