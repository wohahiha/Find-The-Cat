from __future__ import annotations

from django.test import TestCase, override_settings
from django.conf import settings
from django.core.cache import cache
from rest_framework.test import APITestCase
from django.utils import timezone
from apps.common.infra import docker_manager

from apps.accounts.models import User
from apps.contests.models import Contest
from apps.challenges.schemas import ChallengeCreateSchema
from apps.challenges.services import ChallengeCreateService
from apps.machines.schemas import MachineStartSchema, MachineStopSchema
from apps.machines.services import MachineStartService, MachineStopService
from apps.machines.models import MachineInstance
from apps.common.tests_utils import AuthenticatedAPIMixin


class MachineServiceTests(TestCase):
    """服务层单测：验证靶机启动与停止流程。"""

    def setUp(self) -> None:
        docker_manager._USE_MOCK = True  # 测试环境不依赖真实 Docker
        now = timezone.now()
        self.contest = Contest.objects.create(
            name="Machine CTF",
            slug="machine-ctf",
            start_time=now - timezone.timedelta(hours=1),
            end_time=now + timezone.timedelta(hours=2),
        )
        self.user = User.objects.create_user(username="player", email="p@example.com", password="Pass1234")
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

    def test_start_and_stop_machine(self):
        schema = MachineStartSchema(contest_slug="machine-ctf", challenge_slug="pwn")
        instance = MachineStartService().execute(self.user, schema)
        self.assertEqual(instance.status, MachineInstance.Status.RUNNING)
        self.assertTrue(instance.port)
        # 动态题目应生成动态 flag
        self.assertTrue(instance.container_id)
        stopped = MachineStopService().execute(self.user, MachineStopSchema(machine_id=instance.id))
        self.assertEqual(stopped.status, MachineInstance.Status.STOPPED)


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
class MachinesAPITestCase(AuthenticatedAPIMixin, APITestCase):
    """Machines 接口冒烟：启动、列表、停止。"""

    @classmethod
    def setUpTestData(cls):
        docker_manager._USE_MOCK = True
        cls.user = User.objects.create_user(username="alice", email="alice@example.com", password="Passw0rd123")
        cls.admin = User.objects.create_superuser(username="wohahiha", email="admin@example.com", password="stevenxu5190")
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

    def setUp(self):
        cache.clear()

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
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(len(resp.data["data"]["items"]) >= 1)
        # 停止
        resp = client.post(f"/api/machines/{machine_id}/stop/", {}, format="json")
        self.assertEqual(resp.status_code, 200)
