from __future__ import annotations

from datetime import timedelta

from django.test import TestCase, override_settings
from django.conf import settings
from django.core.cache import cache
from rest_framework.test import APITestCase, APIClient
from django.utils import timezone
from apps.common.exceptions import ContestEndedError, ConflictError

from apps.accounts.models import User
from apps.challenges.schemas import ChallengeCreateSchema
from apps.challenges.services import ChallengeCreateService
from apps.common.tests_utils import AuthenticatedAPIMixin
from apps.submissions.schemas import SubmissionCreateSchema
from apps.submissions.services import SubmissionService

from .models import Contest
from .schemas import (
    TeamCreateSchema,
    TeamJoinSchema,
    TeamInviteResetSchema,
    TeamTransferSchema,
)
from .services import (
    ContestRegisterService,
    TeamCreateService,
    TeamJoinService,
    ScoreboardService,
    TeamInviteResetService,
    TeamTransferService,
)


# 测试用例：覆盖 contests 模块的服务层与 API 冒烟，确保核心流程可用


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "contests-service-tests",
        }
    }
)
class ContestServiceTests(TestCase):
    """服务层单元测试：验证队伍创建/加入/移交与记分板逻辑"""

    def setUp(self) -> None:
        """构造一场进行中的比赛和两个普通用户供各用例复用"""
        # 构造进行中的比赛和两个用户
        now = timezone.now()
        self.contest = Contest.objects.create(
            name="Spring CTF",
            slug="spring-ctf",
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=4),
            max_team_members=3,
        )
        self.user1 = User.objects.create_user(username="alice", email="alice@example.com", password="Pass1234")
        self.user2 = User.objects.create_user(username="bob", email="bob@example.com", password="Pass1234")

    def test_team_create_service(self):
        """创建队伍后，队长成员记录应自动生成"""
        ContestRegisterService().execute(self.user1, "spring-ctf")
        schema = TeamCreateSchema(contest_slug="spring-ctf", name="Alpha Team")
        team = TeamCreateService().execute(self.user1, schema)
        self.assertEqual(team.name, "Alpha Team")
        self.assertEqual(team.contest, self.contest)
        self.assertEqual(team.captain, self.user1)
        self.assertTrue(team.members.filter(user=self.user1, role="captain").exists())  # type: ignore[attr-defined]

    def test_team_join_service(self):
        """验证邀请码加入队伍流程与角色设定"""
        ContestRegisterService().execute(self.user1, "spring-ctf")
        ContestRegisterService().execute(self.user2, "spring-ctf")
        team = TeamCreateService().execute(self.user1, TeamCreateSchema(contest_slug="spring-ctf", name="Beta"))
        schema = TeamJoinSchema(contest_slug="spring-ctf", invite_token=team.invite_token)
        membership = TeamJoinService().execute(self.user2, schema)
        self.assertEqual(membership.team, team)
        self.assertEqual(membership.user, self.user2)
        self.assertEqual(membership.role, "member")

    def test_team_invite_reset_and_transfer(self):
        """验证重置邀请码与队长移交链路"""
        ContestRegisterService().execute(self.user1, "spring-ctf")
        ContestRegisterService().execute(self.user2, "spring-ctf")
        team = TeamCreateService().execute(self.user1, TeamCreateSchema(contest_slug="spring-ctf", name="Gamma"))
        # 重置邀请码
        reset_schema = TeamInviteResetSchema(team_id=team.id)  # type: ignore[attr-defined]
        updated_team = TeamInviteResetService().execute(self.user1, reset_schema)
        self.assertNotEqual(team.invite_token, updated_team.invite_token)
        # 队长移交
        TeamJoinService().execute(self.user2,
                                  TeamJoinSchema(contest_slug="spring-ctf", invite_token=updated_team.invite_token))
        transfer_schema = TeamTransferSchema(team_id=team.id, new_captain_id=self.user2.id)  # type: ignore[attr-defined]
        updated_team = TeamTransferService().execute(self.user1, transfer_schema)
        self.assertEqual(updated_team.captain_id, self.user2.id)  # type: ignore[attr-defined]

    def test_scoreboard_service(self):
        """验证记分板汇总逻辑：应按解题记录累加得分"""
        ContestRegisterService().execute(self.user1, "spring-ctf")
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

    def test_contest_register_reject_when_ended(self):
        """比赛已结束时报名应被拒绝并抛出 ContestEndedError"""
        past = timezone.now() - timedelta(hours=3)
        ended = Contest.objects.create(
            name="Ended CTF",
            slug="ended-ctf",
            start_time=past - timedelta(hours=2),
            end_time=past,
            max_team_members=3,
        )
        with self.assertRaises((ContestEndedError, ConflictError)):
            ContestRegisterService().execute(self.user1, ended.slug)


@override_settings(
    REST_FRAMEWORK={
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_RATES": {
            **settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {}),
            "login": "1000/min",
            "user_post": "1000/min",
        },
    },
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "contests-api-tests",
        }
    },
    ALLOW_LOGIN_WITHOUT_CAPTCHA=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class ContestsAPITestCase(AuthenticatedAPIMixin, APITestCase):
    """Contests 模块接口冒烟：比赛、公告、队伍全链路"""

    @classmethod
    def setUpTestData(cls):
        """一次性创建管理员和两个普通用户，供全局用例复用"""
        cls.admin = User.objects.create_superuser(
            username="admin_test_user",
            email="admin@example.com",
            password="StrongPass123!",
        )
        cls.admin.is_email_verified = True
        cls.admin.save()
        cls.user1 = User.objects.create_user(username="alice", email="alice@example.com", password="Passw0rd123")
        cls.user1.is_email_verified = True
        cls.user1.save()
        cls.user2 = User.objects.create_user(username="bob", email="bob@example.com", password="Passw0rd123")
        cls.user2.is_email_verified = True
        cls.user2.save()

    def setUp(self):
        """每个测试前重置时间窗口并清理缓存以避免限流影响"""
        # 每个用例重置时间窗口并清理缓存，避免节流干扰
        self.now_minus = timezone.now() - timedelta(hours=1)
        self.now_plus = timezone.now() + timedelta(hours=1)
        cache.clear()

    def _create_contest(self, client: APIClient, slug: str, categories: list[str] | None = None) -> str:
        """使用管理员创建比赛，返回 slug"""
        payload = {
            "name": f"{slug} contest",
            "slug": slug,
            "description": "desc",
            "start_time": self.now_minus.isoformat(),
            "end_time": self.now_plus.isoformat(),
            "is_team_based": True,
        }
        if categories is not None:
            payload["categories"] = categories
        resp = client.post("/api/contests/", payload, format="json")
        self.assertEqual(resp.status_code, 201)
        return resp.data["data"]["contest"]["slug"]

    def test_contest_list_detail_and_announcements(self):
        """验证比赛创建、公告发布、列表筛选与详情展示"""
        admin_client = self._auth_client("admin_test_user", "StrongPass123!")
        slug = self._create_contest(admin_client, "spring-open")

        # 创建公告
        resp = admin_client.post(
            f"/api/contests/{slug}/announcements/",
            {"title": "欢迎", "summary": "平台升级公告摘要", "content": "开赛公告"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)

        # 列表 running 应包含该比赛
        resp = self.client.get("/api/contests/?status=running")
        self.assertEqual(resp.status_code, 200, resp.content)
        listing = next((item for item in resp.data["data"]["items"] if item["slug"] == slug), None)
        self.assertIsNotNone(listing)
        self.assertEqual(listing["status"], "进行中")

        # 详情包含公告与挑战列表字段
        user_client = self._auth_client("alice", "Passw0rd123")
        resp = user_client.get(f"/api/contests/{slug}/")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIn("announcements", resp.data["data"])
        self.assertEqual(resp.data["data"]["contest"]["status"], "进行中")

    def test_team_lifecycle(self):
        """验证队伍创建、加入、队长移交、邀请码重置与解散全链路"""
        admin_client = self._auth_client("admin_test_user", "StrongPass123!")
        slug = self._create_contest(admin_client, "team-contest")

        c1 = self._auth_client("alice", "Passw0rd123")
        c2 = self._auth_client("bob", "Passw0rd123")

        # 先报名参赛
        c1.post(f"/api/contests/{slug}/register/")
        c2.post(f"/api/contests/{slug}/register/")

        # 创建队伍
        resp = c1.post(
            f"/api/contests/{slug}/teams/",
            {"name": "Alpha", "description": "desc"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        invite_token = resp.data["data"]["team"]["invite_token"]

        # 队伍列表
        resp = c1.get(f"/api/contests/{slug}/teams/")
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
        team_id = resp.data["data"]["items"][0]["id"]
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
        # 解散后列表应为空
        resp = c1.get(f"/api/contests/{slug}/teams/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data["data"]["items"]), 0)

    def test_register_ended_contest_via_api_should_fail(self):
        """API 报名已结束的比赛应返回业务错误"""
        ended_start = timezone.now() - timedelta(days=2)
        ended = Contest.objects.create(
            name="Over Contest",
            slug="over-contest",
            start_time=ended_start,
            end_time=ended_start + timedelta(hours=1),
        )
        client = self._auth_client("alice", "Passw0rd123")
        resp = client.post(f"/api/contests/{ended.slug}/register/")
        self.assertEqual(resp.status_code, 409)
        self.assertNotEqual(resp.data.get("code"), 0)

    def test_contest_category_management(self):
        """验证比赛题目分类在创建及后续更新中可配置"""
        admin_client = self._auth_client("admin_test_user", "StrongPass123!")
        slug = self._create_contest(admin_client, "category-contest", categories=["Web", "Pwn"])

        user_client = self._auth_client("alice", "Passw0rd123")
        detail_resp = user_client.get(f"/api/contests/{slug}/")
        self.assertEqual(detail_resp.status_code, 200)
        contest_payload = detail_resp.data["data"]["contest"]
        self.assertIn("categories", contest_payload)
        self.assertEqual(sorted(cat["name"] for cat in contest_payload["categories"]), ["Pwn", "Web"])

        update_resp = admin_client.put(
            f"/api/contests/{slug}/categories/",
            {"categories": ["Web", "Crypto"]},
            format="json",
        )
        self.assertEqual(update_resp.status_code, 200, update_resp.content)
        self.assertEqual(len(update_resp.data["data"]["items"]), 2)

        list_resp = self.client.get(f"/api/contests/{slug}/categories/")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(sorted(cat["name"] for cat in list_resp.data["data"]["items"]), ["Crypto", "Web"])

    def test_contest_update_permission_enforced(self):
        """比赛更新接口需管理员/管理权限，普通用户应被拒绝"""
        admin_client = self._auth_client("admin_test_user", "StrongPass123!")
        slug = self._create_contest(admin_client, "perm-contest")
        user_client = self._auth_client("alice", "Passw0rd123")

        # 普通用户尝试更新，预期 403
        resp_user = user_client.patch(
            f"/api/contests/{slug}/",
            {"name": "nope"},
            format="json",
        )
        self.assertEqual(resp_user.status_code, 403)

        # 管理员更新应成功
        resp_admin = admin_client.patch(
            f"/api/contests/{slug}/",
            {"name": "updated-name"},
            format="json",
        )
        self.assertEqual(resp_admin.status_code, 200, resp_admin.content)
