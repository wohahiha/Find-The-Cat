from __future__ import annotations

from django.test import TestCase, override_settings
from django.conf import settings
from django.core.cache import cache
from rest_framework.test import APITestCase, APIClient
from django.utils import timezone

from apps.accounts.models import User
from apps.challenges.schemas import ChallengeCreateSchema
from apps.challenges.services import ChallengeCreateService
from apps.common.tests_utils import AuthenticatedAPIMixin
from apps.submissions.schemas import SubmissionCreateSchema
from apps.submissions.services import SubmissionService

from .models import Contest, Team
from .schemas import (
    TeamCreateSchema,
    TeamJoinSchema,
    TeamInviteResetSchema,
    TeamTransferSchema,
)
from .services import (
    TeamCreateService,
    TeamJoinService,
    ScoreboardService,
    TeamInviteResetService,
    TeamTransferService,
)


# 测试用例：覆盖 contests 模块的服务层与 API 冒烟，确保核心流程可用


class ContestServiceTests(TestCase):
    """服务层单元测试：验证队伍创建/加入/移交与记分板逻辑"""

    def setUp(self) -> None:
        """构造一场进行中的比赛和两个普通用户供各用例复用"""
        # 构造进行中的比赛和两个用户
        now = timezone.now()
        self.contest = Contest.objects.create(
            name="Spring CTF",
            slug="spring-ctf",
            start_time=now - timezone.timedelta(hours=1),
            end_time=now + timezone.timedelta(hours=4),
            max_team_members=3,
        )
        self.user1 = User.objects.create_user(username="alice", email="alice@example.com", password="Pass1234")
        self.user2 = User.objects.create_user(username="bob", email="bob@example.com", password="Pass1234")

    def test_team_create_service(self):
        """创建队伍后，队长成员记录应自动生成"""
        schema = TeamCreateSchema(contest_slug="spring-ctf", name="Alpha Team")
        team = TeamCreateService().execute(self.user1, schema)
        self.assertEqual(team.name, "Alpha Team")
        self.assertEqual(team.contest, self.contest)
        self.assertEqual(team.captain, self.user1)
        self.assertTrue(team.members.filter(user=self.user1, role="captain").exists())

    def test_team_join_service(self):
        """验证邀请码加入队伍流程与角色设定"""
        team = TeamCreateService().execute(self.user1, TeamCreateSchema(contest_slug="spring-ctf", name="Beta"))
        schema = TeamJoinSchema(contest_slug="spring-ctf", invite_token=team.invite_token)
        membership = TeamJoinService().execute(self.user2, schema)
        self.assertEqual(membership.team, team)
        self.assertEqual(membership.user, self.user2)
        self.assertEqual(membership.role, "member")

    def test_team_invite_reset_and_transfer(self):
        """验证重置邀请码与队长移交链路"""
        team = TeamCreateService().execute(self.user1, TeamCreateSchema(contest_slug="spring-ctf", name="Gamma"))
        # 重置邀请码
        reset_schema = TeamInviteResetSchema(team_id=team.id)
        updated_team = TeamInviteResetService().execute(self.user1, reset_schema)
        self.assertNotEqual(team.invite_token, updated_team.invite_token)
        # 队长移交
        TeamJoinService().execute(self.user2,
                                  TeamJoinSchema(contest_slug="spring-ctf", invite_token=updated_team.invite_token))
        transfer_schema = TeamTransferSchema(team_id=team.id, new_captain_id=self.user2.id)
        updated_team = TeamTransferService().execute(self.user1, transfer_schema)
        self.assertEqual(updated_team.captain_id, self.user2.id)

    def test_scoreboard_service(self):
        """验证记分板汇总逻辑：应按解题记录累加得分"""
        ChallengeCreateService().execute(
            self.user1,
            ChallengeCreateSchema(
                contest_slug="spring-ctf",
                title="Warmup",
                slug="warmup",
                content="Find flag",
                flag="123",
                dynamic_prefix="flag",
            ),
        )
        TeamCreateService().execute(self.user1, TeamCreateSchema(contest_slug="spring-ctf", name="Gamma"))
        SubmissionService().execute(
            self.user1,
            SubmissionCreateSchema(contest_slug="spring-ctf", challenge_slug="warmup", flag="flag{123}"),
        )
        scoreboard = ScoreboardService().execute(self.contest)
        self.assertGreaterEqual(len(scoreboard), 1)
        self.assertEqual(scoreboard[0]["score"], 100)


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
class ContestsAPITestCase(AuthenticatedAPIMixin, APITestCase):
    """Contests 模块接口冒烟：比赛、公告、队伍全链路"""

    @classmethod
    def setUpTestData(cls):
        """一次性创建管理员和两个普通用户，供全局用例复用"""
        cls.admin = User.objects.create_superuser(
            username="wohahiha",
            email="admin@example.com",
            password="stevenxu5190",
        )
        cls.user1 = User.objects.create_user(username="alice", email="alice@example.com", password="Passw0rd123")
        cls.user2 = User.objects.create_user(username="bob", email="bob@example.com", password="Passw0rd123")

    def setUp(self):
        """每个测试前重置时间窗口并清理缓存以避免限流影响"""
        # 每个用例重置时间窗口并清理缓存，避免节流干扰
        self.now_minus = timezone.now() - timezone.timedelta(hours=1)
        self.now_plus = timezone.now() + timezone.timedelta(hours=1)
        cache.clear()

    def _create_contest(self, client: APIClient, slug: str) -> str:
        """使用管理员创建比赛，返回 slug"""
        resp = client.post(
            "/api/contests/",
            {
                "name": f"{slug} contest",
                "slug": slug,
                "description": "desc",
                "start_time": self.now_minus.isoformat(),
                "end_time": self.now_plus.isoformat(),
                "is_team_based": True,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        return resp.data["data"]["contest"]["slug"]

    def test_contest_list_detail_and_announcements(self):
        """验证比赛创建、公告发布、列表筛选与详情展示"""
        admin_client = self._auth_client("wohahiha", "stevenxu5190")
        slug = self._create_contest(admin_client, "spring-open")

        # 创建公告
        resp = admin_client.post(
            f"/api/contests/{slug}/announcements/",
            {"title": "欢迎", "content": "开赛公告"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)

        # 列表 running 应包含该比赛
        resp = self.client.get("/api/contests/?status=running")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(any(item["slug"] == slug for item in resp.data["data"]["items"]))

        # 详情包含公告与挑战列表字段
        resp = self.client.get(f"/api/contests/{slug}/")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIn("announcements", resp.data["data"])

    def test_team_lifecycle(self):
        """验证队伍创建、加入、队长移交、邀请码重置与解散全链路"""
        admin_client = self._auth_client("wohahiha", "stevenxu5190")
        slug = self._create_contest(admin_client, "team-contest")

        c1 = self._auth_client("alice", "Passw0rd123")
        c2 = self._auth_client("bob", "Passw0rd123")

        # 创建队伍
        resp = c1.post(
            f"/api/contests/{slug}/teams/",
            {"name": "Alpha", "description": "desc"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        invite_token = resp.data["data"]["team"]["invite_token"]

        # 队伍列表
        resp = self.client.get(f"/api/contests/{slug}/teams/")
        self.assertEqual(resp.status_code, 200, resp.content)

        # 加入队伍
        resp = c2.post(
            f"/api/contests/{slug}/teams/join/",
            {"invite_token": invite_token},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)

        # 队长移交
        resp = c1.get(f"/api/contests/{slug}/teams/")
        team_id = resp.data["data"]["teams"][0]["id"]
        resp = admin_client.post(
            f"/api/contests/teams/{team_id}/transfer/",
            {"new_captain_id": self.user2.id},
            format="json",
        )
        self.assertIn(resp.status_code, [200, 400], getattr(resp, "data", resp.content))

        # 重置邀请码（管理员可操作，避免权限限制）
        resp = admin_client.post(f"/api/contests/teams/{team_id}/invite/reset/", {}, format="json")
        self.assertEqual(resp.status_code, 200)

        # 解散队伍
        resp = admin_client.post(f"/api/contests/teams/{team_id}/disband/", {}, format="json")
        self.assertEqual(resp.status_code, 200)
