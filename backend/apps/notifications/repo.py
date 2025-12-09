from __future__ import annotations

from typing import Optional

from django.utils import timezone

from apps.common.base.base_repo import BaseRepo

from .models import Notification


class NotificationRepo(BaseRepo[Notification]):
    """通知仓储：封装常用查询与写入"""

    model = Notification

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("contest", "team", "challenge")
        )

    def unread_count(self, user) -> int:
        return self.filter(user=user, read_at__isnull=True).count()

    def mark_all_read(self, user) -> int:
        now = timezone.now()
        qs = self.filter(user=user, read_at__isnull=True)
        return qs.update(read_at=now)

    def get_by_dedup(self, user, dedup_key: str) -> Optional[Notification]:
        if not dedup_key:
            return None
        return self.filter(user=user, dedup_key=dedup_key).first()

