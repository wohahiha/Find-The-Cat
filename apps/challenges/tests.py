from __future__ import annotations

from django.test import TestCase, override_settings
from django.conf import settings
from django.core.cache import cache
from rest_framework.test import APITestCase, APIClient
from django.utils import timezone

from apps.accounts.models import User
from apps.contests.models import Contest
from apps.contests.schemas import TeamCreateSchema
from apps.contests.services import TeamCreateService

from .schemas import ChallengeCreateSchema, ChallengeSubmitSchema
from .services import ChallengeCreateService, ChallengeSubmitService
from .repo import ChallengeRepo

# 测试用例：覆盖题目创建/提交的服务逻辑与 API 冒烟。


class ChallengeServiceTests(TestCase):
    """服务层单测：验证创建题目与提交 Flag 成功路径。"""
    def setUp(self) -> None:
        # 构造进行中的比赛与出题人/选手
        now = timezone.now()
        self.contest = Contest.objects.create(
            name="Autumn CTF",
            slug="autumn-ctf",
            start_time=now - timezone.timedelta(hours=1),
            end_time=now + timezone.timedelta(hours=5),
        )
        self.author = User.objects.create_user(username="author", email="author@example.com", password="Pass1234")
        self.player = User.objects.create_user(username="player", email="player@example.com", password="Pass1234")

    def test_challenge_create_and_fetch(self):
        """创建题目后可通过仓储按 slug 获取。"""
        schema = ChallengeCreateSchema(
            contest_slug="autumn-ctf",
            title="Warmup",
            slug="warmup",
            content="Find the flag",
            flag="flag{demo}",
            category="Misc",
        )
        challenge = ChallengeCreateService().execute(self.author, schema)
        self.assertEqual(challenge.title, "Warmup")
        repo = ChallengeRepo()
        fetched = repo.get_by_slug(contest=self.contest, slug="warmup")
        self.assertEqual(fetched.title, "Warmup")

    def test_challenge_submit_success(self):
        """成功提交正确 Flag，生成解题记录。"""
        ChallengeCreateService().execute(
            self.author,
            ChallengeCreateSchema(
                contest_slug="autumn-ctf",
                title="Warmup",
                slug="warmup",
                content="Find the flag",
                flag="flag{demo}",
                category="Misc",
            ),
        )
        TeamCreateService().execute(
            self.player,
            TeamCreateSchema(contest_slug="autumn-ctf", name="Solo"),
        )
        schema = ChallengeSubmitSchema(flag="flag{demo}")
        solve = ChallengeSubmitService().execute(
            self.player,
            contest_slug="autumn-ctf",
            challenge_slug="warmup",
            schema=schema,
        )
        self.assertEqual(solve.user, self.player)
        self.assertEqual(solve.challenge.slug, "warmup")


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
class ChallengesAPITestCase(APITestCase):
    """Challenges 模块接口冒烟：题目 CRUD、提交 Flag。"""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(
            username="wohahiha",
            email="admin@example.com",
            password="stevenxu5190",
        )
        cls.player = User.objects.create_user(username="alice", email="alice@example.com", password="Passw0rd123")
        now = timezone.now()
        cls.contest = Contest.objects.create(
            name="API CTF",
            slug="api-ctf",
            start_time=now - timezone.timedelta(hours=1),
            end_time=now + timezone.timedelta(hours=1),
        )

    def _login(self, identifier: str, password: str) -> str:
        """登录获取 JWT。"""
        resp = self.client.post(
            "/api/accounts/auth/login/",
            {"identifier": identifier, "password": password},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        return resp.data["data"]["access"]

    def _auth_client(self, identifier: str, password: str) -> APIClient:
        """返回带 Authorization 的客户端。"""
        token = self._login(identifier, password)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return client

    def test_challenge_crud_and_submit(self):
        """接口链路冒烟：创建题目、列表/详情查看、提交 Flag 与重复提交校验。"""
        admin_client = self._auth_client("wohahiha", "stevenxu5190")
        player_client = self._auth_client("alice", "Passw0rd123")

        # 创建题目（含子任务/附件）
        resp = admin_client.post(
            f"/api/contests/{self.contest.slug}/challenges/",
            {
                "title": "Warmup",
                "slug": "warmup",
                "content": "Find flag",
                "flag": "flag{demo}",
                "base_points": 200,
                "tasks": [
                    {"title": "Step1", "points": 50},
                    {"title": "Step2", "points": 50},
                ],
                "attachments": [
                    {"name": "readme", "url": "https://example.com/readme"},
                ],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)

        # 列表
        resp = player_client.get(f"/api/contests/{self.contest.slug}/challenges/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(any(ch["slug"] == "warmup" for ch in resp.data["data"]["items"]))

        # 详情
        resp = player_client.get(f"/api/contests/{self.contest.slug}/challenges/warmup/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("tasks", resp.data["data"]["challenge"])

        # 提交正确 Flag
        resp = player_client.post(
            f"/api/contests/{self.contest.slug}/challenges/warmup/submit/",
            {"flag": "flag{demo}"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        # 重复提交应返回业务错误
        resp = player_client.post(
            f"/api/contests/{self.contest.slug}/challenges/warmup/submit/",
            {"flag": "flag{demo}"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
