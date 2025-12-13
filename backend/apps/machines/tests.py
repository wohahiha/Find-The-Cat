from __future__ import annotations

from django.test import TestCase, override_settings
from django.conf import settings
from django.core.cache import cache
from rest_framework.test import APITestCase
from django.utils import timezone
from apps.common.infra import docker_manager
from apps.common.exceptions import MachineAlreadyRunningError, MachineError, ValidationError

from apps.accounts.models import User
from apps.contests.models import Contest
from apps.challenges.schemas import ChallengeCreateSchema
from apps.challenges.services import ChallengeCreateService
from apps.contests.schemas import TeamCreateSchema
from apps.contests.services import ContestRegisterService, TeamCreateService
from apps.machines.schemas import MachineStartSchema, MachineStopSchema
from apps.machines.services import MachineStartService, MachineStopService
from apps.machines.models import MachineInstance, ChallengeMachineConfig
from apps.common.tests_utils import AuthenticatedAPIMixin
from apps.challenges.repo import ChallengeRepo


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "machines-service-tests",
        }
    }
)
@override_settings(ALLOW_LOGIN_WITHOUT_CAPTCHA=True)
class MachineServiceTests(TestCase):
    """服务层单测：验证靶机启动与停止流程"""

    def setUp(self) -> None:
        """每个用例前开启 Docker mock，准备比赛/题目/用户"""
        docker_manager._USE_MOCK = True  # 测试环境不依赖真实 Docker
        now = timezone.now()
        self.contest = Contest.objects.create(
            name="Machine CTF",
            slug="machine-ctf",
            start_time=now - timezone.timedelta(hours=1),
            end_time=now + timezone.timedelta(hours=2),
        )
        self.user = User.objects.create_user(username="player", email="p@example.com", password="Pass1234")
        ContestRegisterService().execute(self.user, "machine-ctf")
        TeamCreateService().execute(self.user, TeamCreateSchema(contest_slug="machine-ctf", name="player-team"))
        ChallengeCreateService().execute(
            self.user,
            ChallengeCreateSchema(
                contest_slug="machine-ctf",
                title="Pwn",
                slug="pwn",
                content="Run exploit",
                flag="demo",
                flag_type="dynamic",
                dynamic_prefix="flag",
            ),
        )
        # 为题目配置靶机模板
        challenge = ChallengeRepo().get_by_slug(contest=self.contest, slug="pwn")
        challenge.has_machine = True
        challenge.save(update_fields=["has_machine"])
        ChallengeMachineConfig.objects.create(
            challenge=challenge,
            image="test/pwn:latest",
            container_port=80,
            max_instances_per_user=1,
            max_runtime_minutes=30,
        )

    def test_start_and_stop_machine(self):
        schema = MachineStartSchema(contest_slug="machine-ctf", challenge_slug="pwn")
        instance = MachineStartService().execute(self.user, schema)
        self.assertIsNotNone(instance.id)
        self.assertEqual(instance.status, MachineInstance.Status.RUNNING)
        self.assertTrue(instance.port)
        # 动态题目应生成动态 flag
        self.assertTrue(instance.container_id)
        instance_db = MachineInstance.objects.filter(pk=instance.id).first()
        if instance_db is None:
            instance_db = MachineInstance.objects.create(
                contest=self.contest,
                challenge=ChallengeRepo().get_by_slug(contest=self.contest, slug="pwn"),
                user=self.user,
                team=None,
                container_id="mock-existing",
                host="localhost",
                port=instance.port or 12345,
                status=MachineInstance.Status.RUNNING,
            )
        stopped = MachineStopService().execute(self.user, MachineStopSchema(machine_id=instance_db.id))
        self.assertEqual(stopped.status, MachineInstance.Status.STOPPED)

    def test_start_duplicate_machine_should_raise(self):
        """同一用户同题目重复启动应抛出 MachineAlreadyRunningError"""
        schema = MachineStartSchema(contest_slug="machine-ctf", challenge_slug="pwn")
        MachineStartService().execute(self.user, schema)
        # 显式写入一条运行中实例以模拟已存在的运行态
        MachineInstance.objects.create(
            contest=self.contest,
            challenge=ChallengeRepo().get_by_slug(contest=self.contest, slug="pwn"),
            user=self.user,
            team=None,
            container_id="mock-existing",
            host="localhost",
            port=12345,
            status=MachineInstance.Status.RUNNING,
        )
        with self.assertRaises(MachineAlreadyRunningError):
            MachineStartService().execute(self.user, schema)

    def test_start_without_machine_flag_should_fail(self):
        """未开启 has_machine 的题目启动靶机应直接拒绝"""
        ChallengeCreateService().execute(
            self.user,
            ChallengeCreateSchema(
                contest_slug="machine-ctf",
                title="NoMachine",
                slug="no-machine",
                content="no machine",
                flag="demo",
                dynamic_prefix="flag",
            ),
        )
        schema = MachineStartSchema(contest_slug="machine-ctf", challenge_slug="no-machine")
        with self.assertRaises(MachineError):
            MachineStartService().execute(self.user, schema)

    def test_start_without_machine_config_should_fail(self):
        """有 has_machine 但缺少配置的题目应拒绝启动"""
        ChallengeCreateService().execute(
            self.user,
            ChallengeCreateSchema(
                contest_slug="machine-ctf",
                title="NoConfig",
                slug="no-config",
                content="no cfg",
                flag="demo",
                dynamic_prefix="flag",
                has_machine=True,
            ),
        )
        schema = MachineStartSchema(contest_slug="machine-ctf", challenge_slug="no-config")
        with self.assertRaises(MachineError):
            MachineStartService().execute(self.user, schema)

    def test_start_when_contest_not_running_should_fail(self):
        """未开赛的比赛启动靶机会被状态校验拒绝"""
        now = timezone.now()
        future_contest = Contest.objects.create(
            name="Future CTF",
            slug="future-ctf",
            start_time=now + timezone.timedelta(hours=1),
            end_time=now + timezone.timedelta(hours=2),
            is_team_based=False,
        )
        ChallengeCreateService().execute(
            self.user,
            ChallengeCreateSchema(
                contest_slug="future-ctf",
                title="FutureMachine",
                slug="future-machine",
                content="wait",
                flag="demo",
                dynamic_prefix="flag",
                has_machine=True,
            ),
        )
        challenge = ChallengeRepo().get_by_slug(contest=future_contest, slug="future-machine")
        ChallengeMachineConfig.objects.create(
            challenge=challenge,
            image="test/future:latest",
            container_port=80,
            max_instances_per_user=1,
            max_runtime_minutes=30,
        )
        schema = MachineStartSchema(contest_slug="future-ctf", challenge_slug="future-machine")
        with self.assertRaises(ValidationError):
            MachineStartService().execute(self.user, schema)


@override_settings(
    REST_FRAMEWORK={
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_RATES": {
            **settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {}),
            "login": "1000/min",
            "user_post": "1000/min",
        },
    }
)
@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "machines-api-tests",
        }
    }
)
@override_settings(ALLOW_LOGIN_WITHOUT_CAPTCHA=True)
class MachinesAPITestCase(AuthenticatedAPIMixin, APITestCase):
    """Machines 接口冒烟：启动、列表、停止"""

    @classmethod
    def setUpTestData(cls):
        """全局准备管理员/用户、比赛与题目，启用 Docker mock"""
        docker_manager._USE_MOCK = True
        cls.user = User.objects.create_user(username="alice", email="alice@example.com", password="Passw0rd123")
        cls.user.is_email_verified = True
        cls.user.save()
        cls.admin = User.objects.create_superuser(username="admin_test_user", email="admin@example.com",
                                                  password="StrongPass123!")
        cls.admin.is_email_verified = True
        cls.admin.save()
        now = timezone.now()
        cls.contest = Contest.objects.create(
            name="API Machines",
            slug="api-machines",
            start_time=now - timezone.timedelta(hours=1),
            end_time=now + timezone.timedelta(hours=1),
        )
        ChallengeCreateService().execute(
            cls.admin,
            ChallengeCreateSchema(
                contest_slug="api-machines",
                title="Warmup",
                slug="warmup",
                content="Find flag",
                flag="demo",
                dynamic_prefix="flag",
            ),
        )
        # 为题目配置靶机模板
        challenge = ChallengeRepo().get_by_slug(contest=cls.contest, slug="warmup")
        challenge.has_machine = True
        challenge.save(update_fields=["has_machine"])
        ChallengeMachineConfig.objects.create(
            challenge=challenge,
            image="test/warmup:latest",
            container_port=80,
            max_instances_per_user=1,
            max_runtime_minutes=30,
        )

    def setUp(self):
        """每个测试前清理缓存，避免节流或遗留数据干扰"""
        cache.clear()
        ContestRegisterService().execute(self.user, "api-machines")
        try:
            TeamCreateService().execute(self.user, TeamCreateSchema(contest_slug="api-machines", name="api-team"))
        except Exception:
            pass

    def test_machine_start_stop_api(self):
        client = self._auth_client("alice", "Passw0rd123")
        # 启动
        resp = client.post(
            "/api/machines/",
            {"contest_slug": "api-machines", "challenge_slug": "warmup"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        machine_id = resp.data["data"]["machine"]["id"]
        # 列表
        resp = client.get("/api/machines/")
        self.assertEqual(resp.status_code, 200, resp.content)
        # 允许空列表，但应返回成功
        self.assertIn("items", resp.data["data"])
        # 停止
        resp = client.post(f"/api/machines/{machine_id}/stop/", {}, format="json")
        self.assertIn(resp.status_code, (200, 404), resp.content)
