from __future__ import annotations

from typing import Any
from datetime import datetime, date

from django.utils import timezone

from apps.common.base.base_service import BaseService
from apps.common.exceptions import NotFoundError
from apps.accounts.models import User
from apps.contests.models import Contest, Team
from apps.challenges.models import Challenge
from apps.common.ws_utils import broadcast_notify

from .models import Notification
from .repo import NotificationRepo


def serialize_notification(notification: Notification) -> dict:
    """通知序列化：用于列表/计数接口"""
    return {
        "id": getattr(notification, "id", None),
        "type": notification.type,
        "title": notification.title,
        "body": notification.body,
        "payload": notification.payload or {},
        "contest": getattr(notification.contest, "slug", None),
        "team_id": getattr(notification.team, "id", None),
        "team_slug": getattr(notification.team, "slug", None),
        "challenge": getattr(notification.challenge, "slug", None),
        "read_at": notification.read_at,
        "expires_at": notification.expires_at,
        "created_at": notification.created_at,
    }


def _normalize_payload(value: Any) -> Any:
    """
    将 payload 中的 datetime/date 等不可序列化对象转换为字符串，避免 JSONField 抛错。
    """
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, list):
        return [_normalize_payload(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_normalize_payload(v) for v in value)
    if isinstance(value, dict):
        return {k: _normalize_payload(v) for k, v in value.items()}
    return value


def build_dedup_key(
        *,
        type: str,
        contest: Contest | None = None,
        team: Team | None = None,
        challenge: Challenge | None = None,
        bucket: str | None = None,
        extra: str | None = None,
) -> str:
    """构造去重键：按类型+关联实体+时间桶/额外标识"""
    parts = [
        f"type:{type}",
        f"contest:{getattr(contest, 'id', '') or ''}",
        f"team:{getattr(team, 'id', '') or ''}",
        f"challenge:{getattr(challenge, 'id', '') or ''}",
    ]
    if bucket:
        parts.append(f"bucket:{bucket}")
    if extra:
        parts.append(f"extra:{extra}")
    return "|".join(parts)


class NotificationCreateService(BaseService[Notification]):
    """
    创建/刷新通知服务：
    - 支持 dedup_key 去重，更新内容并重置已读状态
    - 只承担写入，不包含推送，推送留给调用方处理
    """

    atomic_enabled = False

    def __init__(self, repo: NotificationRepo | None = None):
        self.repo = repo or NotificationRepo()

    def perform(
            self,
            user: User,
            *,
            type: str,
            title: str,
            body: str | None = None,
            payload: dict | None = None,
            contest: Contest | None = None,
            team: Team | None = None,
            challenge: Challenge | None = None,
            dedup_key: str | None = None,
            expires_at=None,
    ) -> Notification:
        payload = _normalize_payload(payload or {})
        dedup_key = dedup_key or ""
        existing = self.repo.get_by_dedup(user=user, dedup_key=dedup_key)
        data = {
            "type": type,
            "title": title,
            "body": body or "",
            "payload": payload,
            "contest": contest,
            "team": team,
            "challenge": challenge,
            "expires_at": expires_at,
        }
        if existing:
            # 更新并重置已读，确保最新内容可见
            data["read_at"] = None
            self.repo.update(existing, {k: v for k, v in data.items() if k != "type" or v is not None})
            return existing
        data.update(
            {
                "user": user,
                "dedup_key": dedup_key,
            }
        )
        return self.repo.create(data)


class NotificationMarkReadService(BaseService[Notification]):
    """标记单条通知已读"""

    def __init__(self, repo: NotificationRepo | None = None):
        self.repo = repo or NotificationRepo()

    def perform(self, user: User, notification_id: int) -> Notification:
        try:
            notif = self.repo.get_by_id(notification_id)
        except Notification.DoesNotExist as exc:  # type: ignore[attr-defined]
            raise NotFoundError(message="通知不存在") from exc
        if notif.user_id != getattr(user, "id", None):
            raise NotFoundError(message="通知不存在")
        if notif.read_at is None:
            notif.read_at = timezone.now()
            notif.save(update_fields=["read_at"])
        return notif


class NotificationMarkAllReadService(BaseService[int]):
    """标记当前用户所有通知为已读，返回更新条数"""

    def __init__(self, repo: NotificationRepo | None = None):
        self.repo = repo or NotificationRepo()

    def perform(self, user: User) -> int:
        return self.repo.mark_all_read(user)


def create_and_push_notification(
        user: User,
        *,
        type: str,
        title: str,
        body: str | None = None,
        payload: dict | None = None,
        contest: Contest | None = None,
        team: Team | None = None,
        challenge: Challenge | None = None,
        dedup_key: str | None = None,
        expires_at=None,
        repo: NotificationRepo | None = None,
) -> Notification:
    """创建通知并通过用户频道推送一份（非阻塞失败忽略）"""
    service = NotificationCreateService(repo=repo)
    notif = service.execute(
        user,
        type=type,
        title=title,
        body=body,
        payload=payload,
        contest=contest,
        team=team,
        challenge=challenge,
        dedup_key=dedup_key,
        expires_at=expires_at,
    )
    try:
        broadcast_notify(
            getattr(user, "id", None),
            {
                "event": "notification",
                "id": getattr(notif, "id", None),
                "type": notif.type,
                "title": notif.title,
                "body": notif.body,
                "payload": notif.payload or {},
                "contest": getattr(notif.contest, "slug", None),
                "team_id": getattr(notif.team, "id", None),
                "team_slug": getattr(notif.team, "slug", None),
                "challenge": getattr(notif.challenge, "slug", None),
                "created_at": getattr(notif, "created_at", None),
            },
        )
    except Exception:
        # 推送失败不影响写入
        pass
    return notif


def fanout_notifications(
        users: list[User],
        *,
        type: str,
        title: str,
        body: str | None = None,
        payload: dict | None = None,
        contest: Contest | None = None,
        team: Team | None = None,
        challenge: Challenge | None = None,
        dedup_key: str | None = None,
        expires_at=None,
        repo: NotificationRepo | None = None,
) -> list[Notification]:
    """向一组用户发送同样的通知，复用同一 dedup_key（可选）"""
    repo = repo or NotificationRepo()
    notifs: list[Notification] = []
    for u in users:
        notifs.append(
            create_and_push_notification(
                u,
                type=type,
                title=title,
                body=body,
                payload=payload,
                contest=contest,
                team=team,
                challenge=challenge,
                dedup_key=dedup_key,
                expires_at=expires_at,
                repo=repo,
            )
        )
    return notifs
