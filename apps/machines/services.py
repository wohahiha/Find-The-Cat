from __future__ import annotations

import secrets
import random
from typing import Optional

from apps.common.base.base_service import BaseService
from apps.common.exceptions import ConflictError, PermissionDeniedError, NotFoundError
from apps.accounts.models import User
from apps.contests.services import ContestContextService
from apps.contests.repo import TeamMemberRepo
from apps.challenges.repo import ChallengeRepo

from .models import MachineInstance
from .repo import MachineRepo
from .schemas import MachineStartSchema, MachineStopSchema

# 服务层：靶机实例生命周期管理，使用 docker_manager/redis_client 占位调用。
try:
    from apps.common.infra import docker_manager
except Exception:  # pragma: no cover
    docker_manager = None


def serialize_machine(machine: MachineInstance) -> dict:
    """靶机实例序列化：返回状态、端口与关联实体。"""
    return {
        "id": machine.id,
        "contest": machine.contest.slug,
        "challenge": machine.challenge.slug,
        "user": machine.user_id,
        "team": machine.team_id,
        "container_id": machine.container_id,
        "host": machine.host,
        "port": machine.port,
        "dynamic_flag": machine.dynamic_flag,
        "status": machine.status,
        "created_at": machine.created_at,
        "updated_at": machine.updated_at,
    }


class MachineStartService(BaseService[MachineInstance]):
    """
    启动靶机服务：
    - 校验比赛进行中、题目开放。
    - 为用户/队伍分配容器与端口，生成动态 Flag（若配置前缀）。
    - 防止同一题目重复运行实例。
    """

    atomic_enabled = True

    def __init__(
        self,
        contest_service: ContestContextService | None = None,
        challenge_repo: ChallengeRepo | None = None,
        member_repo: TeamMemberRepo | None = None,
        machine_repo: MachineRepo | None = None,
    ):
        self.contest_service = contest_service or ContestContextService()
        self.challenge_repo = challenge_repo or ChallengeRepo()
        self.member_repo = member_repo or TeamMemberRepo()
        self.machine_repo = machine_repo or MachineRepo()

    def perform(self, user: User, schema: MachineStartSchema) -> MachineInstance:
        # 1) 获取比赛与题目，校验比赛进行中且题目开放
        contest = self.contest_service.get_contest(schema.contest_slug)
        self.contest_service.ensure_contest_running(contest)
        challenge = self.challenge_repo.get_by_slug(contest=contest, slug=schema.challenge_slug)
        if not challenge.is_active:
            raise ConflictError(message="题目未开放，无法启动靶机")

        # 2) 获取队伍关系
        membership = self.member_repo.get_membership(contest=contest, user=user)

        # 3) 防止重复实例：同一用户/题目存在运行实例则拒绝
        running_exists = self.machine_repo.filter(
            contest=contest,
            challenge=challenge,
            user=user,
            status=MachineInstance.Status.RUNNING,
        ).exists()
        if running_exists:
            raise ConflictError(message="已有运行中的靶机实例，请先停止再创建")

        # 4) 生成端口与动态 Flag（占位逻辑）
        port = self._allocate_port()
        dynamic_flag = ""
        if challenge.flag_type == challenge.FlagType.DYNAMIC:
            dynamic_flag = f"{challenge.dynamic_prefix}{secrets.token_hex(4)}"

        # 5) 启动容器（占位调用 docker_manager，如未实现则使用假 ID）
        container_id = self._start_container_stub(challenge_slug=challenge.slug, port=port)

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
                "dynamic_flag": dynamic_flag,
                "status": MachineInstance.Status.RUNNING,
            }
        )
        return instance

    def _allocate_port(self) -> int:
        """占位端口分配：简单随机，未来可接入 redis 分配池。"""
        return random.randint(20000, 40000)

    def _start_container_stub(self, challenge_slug: str, port: int) -> str:
        """调用 docker_manager 启动容器的占位实现。"""
        if docker_manager and hasattr(docker_manager, "start_container"):
            try:
                return docker_manager.start_container(challenge_slug, port=port)  # type: ignore[arg-type]
            except Exception:
                return f"mock-{secrets.token_hex(4)}"
        return f"mock-{secrets.token_hex(4)}"


class MachineStopService(BaseService[MachineInstance]):
    """
    停止靶机服务：
    - 校验操作者为实例创建者、所属队伍成员或管理员。
    - 关闭容器（占位）并更新状态。
    """

    atomic_enabled = True

    def __init__(self, machine_repo: MachineRepo | None = None):
        self.machine_repo = machine_repo or MachineRepo()

    def perform(self, user: User, schema: MachineStopSchema) -> MachineInstance:
        instance = self.machine_repo.get_by_id(schema.machine_id)
        # 权限：管理员或本实例关联用户/队伍
        if not (user.is_staff or instance.user_id == user.id or (instance.team and self._user_in_team(user, instance.team_id))):
            raise PermissionDeniedError(message="无权停止该靶机")

        # 停止容器占位
        self._stop_container_stub(instance.container_id)

        instance.status = MachineInstance.Status.STOPPED
        instance.container_id = instance.container_id or ""
        instance.save(update_fields=["status", "updated_at", "container_id"])
        return instance

    def _user_in_team(self, user: User, team_id: Optional[int]) -> bool:
        return False  # 简化处理：若需校验队伍成员可接入 TeamMemberRepo

    def _stop_container_stub(self, container_id: str) -> None:
        if docker_manager and hasattr(docker_manager, "stop_container"):
            try:
                docker_manager.stop_container(container_id)
            except Exception:
                return
        return
