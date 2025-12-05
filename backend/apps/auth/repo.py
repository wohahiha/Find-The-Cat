# -*- coding: utf-8 -*-
"""
认证与权限数据访问层

基于 BaseRepo，后续可扩展角色/权限的查询与缓存封装。
"""

from apps.common.base.base_repo import BaseRepo


class RBACRepo(BaseRepo):
    """
    RBAC 数据访问仓储
    """

    # TODO: 待角色/权限模型确定后补充查询方法
    pass
