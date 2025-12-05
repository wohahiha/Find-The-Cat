from __future__ import annotations

from datetime import timedelta
import time

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.common.infra import docker_manager, redis_client
from apps.common.infra.logger import get_logger, logger_extra
from apps.common.utils.redis_keys import machine_ports_key

from .repo import MachineRepo
from .services import broadcast_machine_status

logger = get_logger(__name__)


def _release_port_from_cache(port: int | None) -> None:
    """从 Redis 端口占用列表中移除指定端口"""
    if port is None:
        return
    key = machine_ports_key()
    used_ports = set(redis_client.get_json(key) or [])
    if port in used_ports:
        used_ports.discard(port)
        # 重新写回，设置短期过期避免脏数据长驻
        redis_client.set_json(key, list(used_ports), ex=300)


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

    cutoff = timezone.now() - timedelta(minutes=max_minutes_global)
    repo = MachineRepo()
    expired_qs = repo.running_before(cutoff).select_related("contest", "challenge", "user")

    cleaned = 0
    for instance in expired_qs:
        container_id = instance.container_id
        port = instance.port
        per_challenge_runtime = getattr(instance.challenge, "machine_config", None)
        max_minutes = getattr(per_challenge_runtime, "max_runtime_minutes", max_minutes_global)
        cutoff_time = timezone.now() - timedelta(minutes=max_minutes)
        if instance.created_at >= cutoff_time:
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
