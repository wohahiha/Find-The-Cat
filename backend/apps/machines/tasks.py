from __future__ import annotations

from datetime import timedelta
import time

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.common.infra import docker_manager, redis_client
from apps.common.infra.logger import get_logger, logger_extra
from .repo import MachineRepo
from .services import broadcast_machine_status, _release_port_lock
from apps.notifications.services import create_and_push_notification, build_dedup_key
from apps.notifications.models import Notification

logger = get_logger(__name__)


def _release_port_from_cache(port: int | None) -> None:
    """从 Redis 端口占用列表中移除指定端口"""
    if port is None:
        return
    _release_port_lock(port)


def _stop_container(container_id: str) -> None:
    """停止并移除容器，容器不存在时忽略异常"""
    if not container_id:
        return
    docker_manager.stop_container(container_id)


@shared_task(name="cleanup_expired_machines")
def cleanup_expired_machines() -> int:
    """
    Celery 定时任务：清理超时运行的靶机容器

    - 判断运行时长是否超过 settings.MACHINE_MAX_RUNTIME_MINUTES
    - 依次停止/移除容器，释放端口缓存，并标记实例为 STOPPED
    - 兼容 mock 模式（docker_manager 内部已处理），异常仅记录日志
    """
    start = time.time()
    max_minutes_global = int(getattr(settings, "MACHINE_MAX_RUNTIME_MINUTES", 30))
    if max_minutes_global <= 0:
        return 0
    logger.info(
        "清理任务开始",
        extra=logger_extra({"default_max_minutes": max_minutes_global}),
    )

    repo = MachineRepo()
    expired_qs = repo.filter(status=repo.model.Status.RUNNING).select_related("contest", "challenge", "user")

    cleaned = 0
    stale_threshold_seconds = max(getattr(settings, "MACHINE_CLEAN_INTERVAL_SECONDS", 300) * 2, 600)
    for instance in expired_qs:
        container_id = instance.container_id
        port = instance.port
        per_challenge_runtime = getattr(instance.challenge, "machine_config", None)
        max_minutes = getattr(per_challenge_runtime, "max_runtime_minutes", max_minutes_global)
        expected_expires = getattr(instance, "expires_at", None) or (instance.created_at + timedelta(minutes=max_minutes))
        remaining_seconds = (expected_expires - timezone.now()).total_seconds()
        # 心跳异常：更新距今超出阈值且未到期
        if remaining_seconds > 0 and (timezone.now() - instance.updated_at).total_seconds() > stale_threshold_seconds:
            try:
                dedup = build_dedup_key(
                    type=Notification.Type.MACHINE_HEARTBEAT_MISS,
                    contest=getattr(instance, "contest", None),
                    challenge=getattr(instance, "challenge", None),
                    extra=f"machine:{instance.id}",
                )
                create_and_push_notification(
                    getattr(instance, "user", None),
                    type=Notification.Type.MACHINE_HEARTBEAT_MISS,
                    title="靶机连接异常",
                    body="检测到靶机心跳异常，建议重启或检查网络",
                    payload={
                        "machine_id": getattr(instance, "id", None),
                        "contest": getattr(getattr(instance, 'contest', None), 'slug', None),
                        "challenge": getattr(getattr(instance, 'challenge', None), 'slug', None),
                        "host": getattr(instance, "host", None),
                        "port": getattr(instance, "port", None),
                        "remaining_seconds": int(remaining_seconds),
                        "reason": "heartbeat_miss",
                    },
                    contest=getattr(instance, "contest", None),
                    challenge=getattr(instance, "challenge", None),
                    dedup_key=dedup,
                    expires_at=expected_expires,
                )
            except Exception:
                pass
        # 即将到期提醒
        threshold_minutes = getattr(settings, "MACHINE_EXPIRING_NOTIFY_MINUTES", 5)
        if 0 < remaining_seconds <= threshold_minutes * 60:
            try:
                bucket = f"{int(remaining_seconds // 60)}m"
                dedup = build_dedup_key(
                    type=Notification.Type.MACHINE_EXPIRING,
                    contest=getattr(instance, "contest", None),
                    challenge=getattr(instance, "challenge", None),
                    extra=f"machine:{instance.id}",
                    bucket=bucket,
                )
                create_and_push_notification(
                    getattr(instance, "user", None),
                    type=Notification.Type.MACHINE_EXPIRING,
                    title="靶机即将到期",
                    body=f"{getattr(instance.challenge, 'title', getattr(instance.challenge, 'slug', '靶机'))} 剩余 {int(remaining_seconds // 60)} 分钟",
                    payload={
                        "machine_id": getattr(instance, "id", None),
                        "contest": getattr(getattr(instance, 'contest', None), 'slug', None),
                        "challenge": getattr(getattr(instance, 'challenge', None), 'slug', None),
                        "host": getattr(instance, "host", None),
                        "port": getattr(instance, "port", None),
                        "remaining_seconds": int(remaining_seconds),
                        "expires_at": expected_expires,
                    },
                    contest=getattr(instance, "contest", None),
                    challenge=getattr(instance, "challenge", None),
                    dedup_key=dedup,
                    expires_at=expected_expires,
                )
            except Exception:
                pass
        if expected_expires >= timezone.now():
            continue
        # noinspection PyBroadException
        try:
            _stop_container(container_id)
            _release_port_from_cache(port)
            repo.mark_stopped(instance, clear_port=True)
            cleaned += 1
            broadcast_machine_status(
                instance,
                event="machine_stopped",
                reason="expired_cleanup",
            )
            try:
                dedup = build_dedup_key(
                    type=Notification.Type.MACHINE_EXPIRED,
                    contest=getattr(instance, "contest", None),
                    challenge=getattr(instance, "challenge", None),
                    extra=f"machine:{instance.id}",
                )
                create_and_push_notification(
                    getattr(instance, "user", None),
                    type=Notification.Type.MACHINE_EXPIRED,
                    title="靶机已回收",
                    body=f"{getattr(instance.challenge, 'title', getattr(instance.challenge, 'slug', '靶机'))} 已到期自动关闭",
                    payload={
                        "machine_id": getattr(instance, "id", None),
                        "contest": getattr(getattr(instance, 'contest', None), 'slug', None),
                        "challenge": getattr(getattr(instance, 'challenge', None), 'slug', None),
                        "host": getattr(instance, "host", None),
                        "port": getattr(instance, "port", None),
                        "expires_at": expected_expires,
                        "reason": "expired_cleanup",
                    },
                    contest=getattr(instance, "contest", None),
                    challenge=getattr(instance, "challenge", None),
                    dedup_key=dedup,
                    expires_at=timezone.now() + timedelta(days=7),
                )
            except Exception:
                pass
            logger.info(
                "自动销毁超时靶机实例",
                extra=logger_extra({
                    "machine_id": instance.id,
                    "container_id": container_id,
                    "user_id": instance.user_id,
                    "contest": getattr(instance.contest, "slug", None),
                    "challenge": getattr(instance.challenge, "slug", None),
                    "port": port,
                }),
            )
        except Exception:  # 扫描到任何异常均记录日志继续下一个实例
            logger.exception(
                "清理超时靶机实例失败",
                extra=logger_extra({
                    "machine_id": instance.id,
                    "container_id": container_id,
                    "user_id": instance.user_id,
                    "contest": getattr(instance.contest, "slug", None),
                    "challenge": getattr(instance.challenge, "slug", None),
                }),
            )
    logger.info(
        "清理任务完成",
        extra=logger_extra(
            {
                "cleaned": cleaned,
                "duration_ms": int((time.time() - start) * 1000),
                "interval": getattr(settings, "MACHINE_CLEAN_INTERVAL_SECONDS", None),
            }
        ),
    )
    return cleaned
