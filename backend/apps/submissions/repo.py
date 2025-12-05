from __future__ import annotations

from apps.common.base.base_repo import BaseRepo

from .models import Submission


# 仓储层：封装提交记录的查询与写入


class SubmissionRepo(BaseRepo[Submission]):
    """提交仓储：提供基本 CRUD，后续可扩展过滤"""

    model = Submission

    def filter_with_related(self, **kwargs):
        """带常用外键的筛选，减少后续访问 N+1"""
        return (
            self.filter(**kwargs)
            .select_related("contest", "challenge", "user", "team", "solve")
        )
