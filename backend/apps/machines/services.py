from __future__ import annotations

import random
from typing import Optional
from contextlib import suppress

from datetime import timedelta
from django.conf import settings
from django.utils import timezone

from apps.common.base.base_service import BaseService
from apps.common.exceptions import (
    ConflictError,
    PermissionDeniedError,
    MachineAlreadyRunningError,
    MachinePortUnavailableError,
    MachineError,
    ValidationError,
)
from apps.accounts.models import User
from apps.contests.services import ContestContextService
from apps.contests.repo import TeamMemberRepo
from apps.challenges.repo import ChallengeRepo

from .models import MachineInstance
from .repo import MachineRepo
from .schemas import MachineStartSchema, MachineStopSchema, MachineExtendSchema

# 服务层：靶机实例生命周期管理，使用 docker_manager/redis_client 占位调用
from apps.common.infra import docker_manager
from apps.common.infra import redis_client
from apps.common.infra.logger import get_logger, logger_extra
from apps.common.utils.redis_keys import machine_ports_key
from apps.notifications.services import create_and_push_notification, build_dedup_key
from apps.notifications.models import Notification

logger = get_logger(__name__)


def serialize_machine(machine: MachineInstance) -> dict:
    """靶机实例序列化：返回状态、端口与关联实体"""
    machine_id = getattr(machine, "id", None)
    config = getattr(machine, "challenge", None) and getattr(machine.challenge, "machine_config", None)
    now = timezone.now()
    expires_at = getattr(machine, "expires_at", None)
    remaining_seconds = None
    if expires_at:
        remaining_seconds = max(int((expires_at - now).total_seconds()), 0)
    max_times = getattr(config, "extend_max_times", None)
    remaining_extend_times = None
    if max_times is not None:
        try:
            max_times_int = int(max_times)
            if max_times_int >= 0:
                remaining_extend_times = max(max_times_int - getattr(machine, "extend_count", 0), 0)
            else:
                remaining_extend_times = -1
        except Exception:
            remaining_extend_times = None
    return {
        "id": machine_id,
        "contest": getattr(getattr(machine, "contest", None), "slug", None),
        "challenge": getattr(getattr(machine, "challenge", None), "slug", None),
        "user": getattr(machine, "user_id", None),
        "team": getattr(machine, "team_id", None),
        "container_id": getattr(machine, "container_id", None),
        # 使用后台配置的对外主机名，未配置则回退实例记录
        "host": getattr(settings, "MACHINE_PUBLIC_HOST", None) or machine.host,
        "port": machine.port,
        "status": machine.status,
        "extend_count": getattr(machine, "extend_count", 0),
        "expires_at": expires_at,
        "remaining_seconds": remaining_seconds,
        "extend_max_times": getattr(config, "extend_max_times", None),
        "extend_threshold_minutes": getattr(config, "extend_threshold_minutes", None),
        "extend_minutes_default": getattr(config, "extend_minutes_default", None),
        "remaining_extend_times": remaining_extend_times,
        "created_at": machine.created_at,
        "updated_at": machine.updated_at,
    }


def broadcast_machine_status(instance: MachineInstance, *, event: str = "machine_status",
                             reason: str | None = None) -> None:
    """
    推送靶机状态心跳：
    - 统一包含 host/port/status，减少前端轮询
    """
    try:
        from apps.common.ws_utils import broadcast_contest, broadcast_notify
    except ImportError:
        return
    payload = {
        "event": event,
        "contest": getattr(instance.contest, "slug", None),
        "challenge": getattr(instance.challenge, "slug", None),
        "machine_id": getattr(instance, "id", None),
        "status": instance.status,
        "host": instance.host,
        "port": instance.port,
        "user_id": getattr(instance, "user_id", None),
        "team_id": getattr(instance, "team_id", None),
        "heartbeat_at": timezone.now().isoformat(),
    }
    if reason:
        payload["reason"] = reason
    user_id = getattr(instance, "user_id", None)
    if user_id:
        broadcast_notify(user_id, payload)
    broadcast_contest(getattr(instance.contest, "slug", ""), payload)


def _release_port_lock(port: int | None) -> None:
    """释放端口锁，并清理遗留缓存集合"""
    if port is None:
        return
    redis_client.release_lock(f"{machine_ports_key()}:lock:{port}")
    key = machine_ports_key()
    try:
        used = set(redis_client.get_json(key) or [])
        if port in used:
            used.discard(port)
            redis_client.set_json(key, list(used), ex=300)
    except Exception:
        # 兼容 Redis 不可用的场景
        pass


class MachineStartService(BaseService[MachineInstance]):
    """
    启动靶机服务：
    - 校验比赛进行中、题目开放
    - 为用户/队伍分配容器与端口，生成动态 Flag（若配置前缀）
    - 防止同一题目重复运行实例
    """

    atomic_enabled = True

    def __init__(
            self,
            contest_service: ContestContextService | None = None,
            challenge_repo: ChallengeRepo | None = None,
            member_repo: TeamMemberRepo | None = None,
            machine_repo: MachineRepo | None = None,
    ):
        """注入比赛上下文、题目、成员与靶机仓储，便于测试替换"""
        self.contest_service = contest_service or ContestContextService()
        self.challenge_repo = challenge_repo or ChallengeRepo()
        self.member_repo = member_repo or TeamMemberRepo()
        self.machine_repo = machine_repo or MachineRepo()

    def perform(self, user: User, schema: MachineStartSchema) -> MachineInstance:
        """启动单个靶机实例，返回创建的实例记录"""
        # 1) 获取比赛与题目，校验比赛进行中且题目开放
        contest = self.contest_service.get_contest(schema.contest_slug)
        self.contest_service.ensure_contest_running(contest)
        challenge = self.challenge_repo.get_by_slug(contest=contest, slug=schema.challenge_slug)
        if not challenge.is_active:
            raise ConflictError(message="题目未开放，无法启动靶机")
        if not getattr(challenge, "has_machine", False):
            raise MachineError(message="该题目未启用靶机")

        # 2) 获取队伍关系
        membership = self.member_repo.get_membership(contest=contest, user=user)
        if contest.is_team_based and membership is None:
            raise PermissionDeniedError(message="该比赛为团队赛，请先加入队伍后再启动靶机")

        # 3) 防止重复实例：同一用户/题目存在运行实例则拒绝
        if self.machine_repo.running_for_user(contest=contest, challenge=challenge, user=user):
            raise MachineAlreadyRunningError()

        config = getattr(challenge, "machine_config", None)
        if not config:
            raise MachineError(message="题目未配置靶机模板，请在后台补充后再试")

        # 4) 生成端口（动态 Flag 由挑战模块负责校验，不在靶机保存）
        port = self._allocate_port(config)

        # 5) 启动容器（占位调用 docker_manager，如未实现则使用假 ID）
        try:
            container_id = self._start_container(challenge=challenge, port=port)
        except Exception:
            _release_port_lock(port)
            raise

        runtime_minutes = int(
            getattr(config, "max_runtime_minutes", None)
            or getattr(settings, "MACHINE_MAX_RUNTIME_MINUTES", 30)
        )
        expires_at = timezone.now() + timedelta(minutes=runtime_minutes)
        remaining_seconds = max(int((expires_at - timezone.now()).total_seconds()), 0)

        # 6) 创建实例记录
        instance = self.machine_repo.create(
            {
                "contest": contest,
                "challenge": challenge,
                "user": user,
                "team": membership.team if membership else None,
                "container_id": container_id,
                "host": "localhost",
                "port": port,
                "status": MachineInstance.Status.RUNNING,
                "expires_at": expires_at,
                "extend_count": 0,
            }
        )
        logger.info(
            "靶机启动成功",
            extra=logger_extra(
                {
                    "machine_id": getattr(instance, "id", None),
                    "contest": getattr(contest, "slug", None),
                    "challenge": getattr(challenge, "slug", None),
                    "user_id": getattr(user, "id", None),
                    "team_id": getattr(membership, "team_id", None),
                    "container_id": container_id,
                    "port": port,
                    "port_cache_ttl": getattr(config, "port_cache_ttl", None),
                }
            ),
        )
        # WebSocket：靶机启动成功事件（附带状态心跳，减少轮询）
        from apps.common.ws_utils import broadcast_contest, broadcast_notify
        heartbeat_at = timezone.now().isoformat()
        machine_id = getattr(instance, "id", None)
        contest_slug = getattr(contest, "slug", None)
        challenge_slug = getattr(challenge, "slug", None)
        user_id = getattr(user, "id", None)
        team_id = getattr(membership, "team_id", None)
        broadcast_notify(
            user_id,
            {
                "event": "machine_started",
                "contest": contest_slug,
                "challenge": challenge_slug,
                "machine_id": machine_id,
                "port": port,
                "team_id": team_id,
                "host": instance.host,
                "status": instance.status,
                "heartbeat_at": heartbeat_at,
            },
        )
        broadcast_contest(
            contest_slug or "",
            {
                "event": "machine_started",
                "contest": contest_slug,
                "challenge": challenge_slug,
                "machine_id": machine_id,
                "port": port,
                "team_id": team_id,
                "user_id": user_id,
                "host": instance.host,
                "status": instance.status,
                "heartbeat_at": heartbeat_at,
            },
        )
        broadcast_machine_status(instance, event="machine_status")
        # 系统通知：启动信息（含端口/到期时间）
        try:
            dedup = build_dedup_key(
                type=Notification.Type.MACHINE_STARTED,
                contest=contest,
                challenge=challenge,
                extra=f"machine:{machine_id}",
            )
            create_and_push_notification(
                user,
                type=Notification.Type.MACHINE_STARTED,
                title=f"靶机已启动：{challenge_slug}",
                body=f"访问 {instance.host}:{port}，到期时间 {expires_at.strftime('%Y-%m-%d %H:%M:%S') if expires_at else '未知'}",
                payload={
                    "machine_id": machine_id,
                    "contest": contest_slug,
                    "challenge": challenge_slug,
                    "host": instance.host,
                    "port": port,
                    "expires_at": expires_at,
                    "remaining_seconds": remaining_seconds,
                },
                contest=contest,
                challenge=challenge,
                dedup_key=dedup,
                expires_at=expires_at,
            )
        except Exception:
            # 通知失败不阻断业务
            pass
        return instance

    def _allocate_port(self, config) -> int:
        """
        使用 redis + db 双重校验的端口分配（简化版）：
        - 先从 redis 集合读占用，如果未配置则回退数据库检查
        """
        used_db = self.machine_repo.running_ports()
        lock_prefix = f"{machine_ports_key()}:lock"
        ttl = int(getattr(config, "port_cache_ttl", 300) or 300)
        fallback_port = None
        for _ in range(200):
            port = random.randint(20000, 40000)
            if port in used_db:
                continue
            lock_key = f"{lock_prefix}:{port}"
            if redis_client.acquire_lock(lock_key, ex=ttl):
                return port
            # 记录一个可用端口以便 Redis 不可用时回退
            if fallback_port is None:
                fallback_port = port
        logger.warning(
            "端口分配失败",
            extra=logger_extra({"used_count": len(used_db), "port_cache_ttl": ttl, "lock_prefix": lock_prefix}),
        )
        if fallback_port is not None:
            return fallback_port
        raise MachinePortUnavailableError()

    @staticmethod
    def _start_container(challenge, port: int) -> str:
        """
        启动容器并返回 ID，支持 mock
        """
        config = getattr(challenge, "machine_config", None)
        image = config.image
        container_port = config.container_port
        env_vars = config.environment or None
        try:
            return docker_manager.start_container(
                image,
                port=port,
                env=env_vars,
                container_port=container_port,
                network=getattr(docker_manager, "DOCKER_NETWORK", None),
            )
        except Exception:  # noqa: BLE001 捕获容器启动的所有异常以统一转换为业务错误
            # 记录异常并提示前端稍后重试，避免产生无法控制的实例记录
            logger.exception(
                "启动靶机容器失败",
                extra=logger_extra({"challenge": challenge.slug, "port": port}),
            )
            # WebSocket：启动失败事件（不包含用户信息，仅挑战/端口）
            with suppress(Exception):
                from apps.common.ws_utils import broadcast_contest

                if getattr(challenge, "contest", None):
                    broadcast_contest(
                        getattr(challenge.contest, "slug", ""),
                        {
                            "event": "machine_failed",
                            "contest": getattr(challenge.contest, "slug", None),
                            "challenge": challenge.slug,
                            "port": port,
                            "status": MachineInstance.Status.ERROR,
                            "heartbeat_at": timezone.now().isoformat(),
                        },
                    )
            raise MachineError(message="靶机启动失败，请稍后重试")


class MachineStopService(BaseService[MachineInstance]):
    """
    停止靶机服务：
    - 校验操作者为实例创建者、所属队伍成员或管理员
    - 关闭容器（占位）并更新状态
    """

    atomic_enabled = True

    def __init__(self, machine_repo: MachineRepo | None = None, member_repo: TeamMemberRepo | None = None):
        """允许注入仓储，便于测试与替换实现"""
        self.machine_repo = machine_repo or MachineRepo()
        self.member_repo = member_repo or TeamMemberRepo()

    def perform(self, user: User, schema: MachineStopSchema) -> MachineInstance:
        """停止指定实例并更新状态，必要时校验团队权限"""
        instance = self.machine_repo.get_by_id(schema.machine_id)
        # 权限：管理员或本实例关联用户/队伍
        user_id = getattr(user, "id", None)
        if not (user.is_staff or getattr(instance, "user_id", None) == user_id or self._user_in_team(user,
                                                                                                     getattr(instance,
                                                                                                             "team_id",
                                                                                                             None))):
            raise PermissionDeniedError(message="无权停止该靶机")

        # 停止容器占位
        self._stop_container(instance.container_id)

        instance.status = MachineInstance.Status.STOPPED
        instance.container_id = instance.container_id or ""
        instance.save(update_fields=["status", "updated_at", "container_id"])
        _release_port_lock(instance.port)
        logger.info(
            "靶机停止",
            extra=logger_extra(
                {
                    "machine_id": getattr(instance, "id", None),
                    "contest": getattr(getattr(instance, "contest", None), "slug", None),
                    "challenge": getattr(getattr(instance, "challenge", None), "slug", None),
                    "user_id": user_id,
                    "team_id": getattr(instance, "team_id", None),
                    "container_id": getattr(instance, "container_id", None),
                    "port": getattr(instance, "port", None),
                }
            ),
        )
        # WebSocket：靶机停止事件
        from apps.common.ws_utils import broadcast_contest, broadcast_notify
        heartbeat_at = timezone.now().isoformat()
        contest_slug = getattr(getattr(instance, "contest", None), "slug", None)
        challenge_slug = getattr(getattr(instance, "challenge", None), "slug", None)
        machine_id = getattr(instance, "id", None)
        team_id = getattr(instance, "team_id", None)
        broadcast_notify(
            user_id,
            {
                "event": "machine_stopped",
                "contest": contest_slug,
                "challenge": challenge_slug,
                "machine_id": machine_id,
                "port": getattr(instance, "port", None),
                "team_id": team_id,
                "host": instance.host,
                "status": instance.status,
                "heartbeat_at": heartbeat_at,
            },
        )
        broadcast_contest(
            contest_slug or "",
            {
                "event": "machine_stopped",
                "contest": contest_slug,
                "challenge": challenge_slug,
                "machine_id": machine_id,
                "port": getattr(instance, "port", None),
                "team_id": team_id,
                "user_id": user_id,
                "host": instance.host,
                "status": instance.status,
                "heartbeat_at": heartbeat_at,
            },
        )
        broadcast_machine_status(instance, event="machine_status")
        return instance

    def _user_in_team(self, user: User, team_id: Optional[int]) -> bool:
        """检查用户是否属于指定队伍（活跃成员）"""
        if team_id is None:
            return False
        membership = self.member_repo.filter(team_id=team_id, user=user, is_active=True).first()
        return membership is not None

    @staticmethod
    def _stop_container(container_id: str) -> None:
        """调用 docker_manager 停止容器，异常时忽略以保证流程可继续"""
        with suppress(Exception):
            docker_manager.stop_container(container_id)


class MachineExtendService(BaseService[MachineInstance]):
    """
    延长靶机时长：
    - 仅运行中的实例可延长
    - 支持全局默认延长分钟数/最大延长次数/可延长时间阈值
    """

    atomic_enabled = True

    def __init__(self, machine_repo: MachineRepo | None = None, member_repo: TeamMemberRepo | None = None):
        self.machine_repo = machine_repo or MachineRepo()
        self.member_repo = member_repo or TeamMemberRepo()

    def perform(self, user: User, schema: MachineExtendSchema) -> MachineInstance:
        instance = self.machine_repo.get_by_id(schema.machine_id)
        user_id = getattr(user, "id", None)
        if not (user.is_staff or getattr(instance, "user_id", None) == user_id or self._user_in_team(user, getattr(instance, "team_id", None))):
            raise PermissionDeniedError(message="无权操作该靶机")

        if instance.status != MachineInstance.Status.RUNNING:
            raise ConflictError(message="仅运行中的靶机可延时")

        config = getattr(instance.challenge, "machine_config", None)
        max_times = getattr(config, "extend_max_times", None)
        if max_times is None:
            max_times = getattr(settings, "MACHINE_EXTEND_MAX_TIMES", -1)
        with suppress(Exception):
            max_times = int(max_times)
        if max_times >= 0 and getattr(instance, "extend_count", 0) >= max_times:
            raise ConflictError(message="已达到最大延时次数")

        minutes = schema.minutes or getattr(config, "extend_minutes_default", None) or getattr(settings, "MACHINE_EXTEND_MINUTES_DEFAULT", 30)
        try:
            minutes = int(minutes)
        except Exception:
            minutes = 30
        if minutes <= 0:
            raise ValidationError(message="延时时间配置无效")

        expires_at = getattr(instance, "expires_at", None) or (instance.created_at + timedelta(minutes=getattr(settings, "MACHINE_MAX_RUNTIME_MINUTES", 30)))
        now = timezone.now()
        remaining_seconds = (expires_at - now).total_seconds()
        threshold = getattr(config, "extend_threshold_minutes", None)
        if threshold is None:
            threshold = getattr(settings, "MACHINE_EXTEND_THRESHOLD_MINUTES", 15)
        with suppress(Exception):
            threshold = int(threshold)
        if threshold > 0 and remaining_seconds > threshold * 60:
            raise ConflictError(message="未到可延时窗口，稍后再试")

        new_expires = expires_at + timedelta(minutes=minutes)
        instance.expires_at = new_expires
        instance.extend_count = getattr(instance, "extend_count", 0) + 1
        instance.save(update_fields=["expires_at", "extend_count", "updated_at"])

        broadcast_machine_status(instance, event="machine_extended")
        return instance

    def _user_in_team(self, user: User, team_id: Optional[int]) -> bool:
        if team_id is None:
            return False
        membership = self.member_repo.filter(team_id=team_id, user=user, is_active=True).first()
        return membership is not None
