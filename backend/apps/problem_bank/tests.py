from __future__ import annotations

from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.common.tests_utils import AuthenticatedAPIMixin
from apps.challenges.schemas import ChallengeCreateSchema
from apps.challenges.services import ChallengeCreateService
from apps.contests.models import Contest
from apps.problem_bank.schemas import (
    ProblemBankCreateSchema,
    BankImportFromContestSchema,
)
from apps.problem_bank.services import (
    ProblemBankCreateService,
    BankImportFromContestService,
    BankExportService,
    BankChallengeSubmitService,
)
from apps.problem_bank.repo import ProblemBankRepo, BankChallengeRepo, BankSolveRepo
from apps.problem_bank.models import BankChallenge, BankCategory, ProblemBank


class ProblemBankServiceTests(TestCase):
    """服务层测试：题库创建、导入、作答与导出"""

    def setUp(self) -> None:
        now = timezone.now()
        self.admin = User.objects.create_superuser(username="admin", email="a@example.com", password="Passw0rd123")
        self.user = User.objects.create_user(username="player", email="p@example.com", password="Passw0rd123")
        self.contest = Contest.objects.create(
            name="Finished CTF",
            slug="finished-ctf",
            start_time=now - timezone.timedelta(days=2),
            end_time=now - timezone.timedelta(days=1),
        )
        ChallengeCreateService().execute(
            self.admin,
            ChallengeCreateSchema(
                contest_slug="finished-ctf",
                title="Bankable",
                slug="bankable",
                content="Solve me",
                flag="demo",
                dynamic_prefix="flag",
            ),
        )
        self.bank = ProblemBankCreateService().execute(
            ProblemBankCreateSchema(name="Review Bank", slug="review-bank", is_public=True)
        )

    def test_import_and_submit_and_export(self):
        # 导入比赛题目
        imported = BankImportFromContestService().execute(
            BankImportFromContestSchema(bank_slug=self.bank.slug, contest_slug="finished-ctf")
        )
        self.assertEqual(len(imported), 1)
        # 作答
        submit_service = BankChallengeSubmitService()
        from apps.problem_bank.schemas import BankChallengeSubmitSchema, BankExportSchema

        solve = submit_service.execute(
            self.user,
            self.bank.slug,
            "bankable",
            BankChallengeSubmitSchema(flag="flag{demo}"),
        )
        self.assertIsNotNone(solve)
        self.assertTrue(BankSolveRepo().has_solved(challenge=imported[0], user=self.user))
        # 导出
        export_payload = BankExportService().execute(BankExportSchema(bank_slug=self.bank.slug))
        self.assertIn("filename", export_payload)
        self.assertIn("content", export_payload)


@override_settings(
    REST_FRAMEWORK={
        **settings.REST_FRAMEWORK,
        "DEFAULT_AUTHENTICATION_CLASSES": ("apps.common.authentication.JWTAuthentication",),
        "DEFAULT_PERMISSION_CLASSES": ("apps.common.permissions.IsAuthenticated",),
        "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    },
    ALLOW_LOGIN_WITHOUT_CAPTCHA=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",   
            "LOCATION": "problem-bank-api-tests",
        }
    },
)
class ProblemBankAPITests(AuthenticatedAPIMixin, APITestCase):
    """接口冒烟：创建题库、导入题目、作答"""

    @classmethod
    def setUpTestData(cls):
        now = timezone.now()
        cls.admin = User.objects.create_superuser(username="admin", email="a@example.com", password="Passw0rd123")
        cls.admin.is_email_verified = True
        cls.admin.save()
        cls.user = User.objects.create_user(username="alice", email="alice@example.com", password="Passw0rd123")
        cls.user.is_email_verified = True
        cls.user.save()
        cls.contest = Contest.objects.create(
            name="Importable",
            slug="importable",
            start_time=now - timezone.timedelta(days=2),
            end_time=now - timezone.timedelta(days=1),
        )
        ChallengeCreateService().execute(
            cls.admin,
            ChallengeCreateSchema(
                contest_slug="importable",
                title="ForBank",
                slug="for-bank",
                content="flag here",
                flag="demo",
                dynamic_prefix="flag",
            ),
        )
        # 预置题库与题库题目（通过服务层导入，避免前端路由依赖管理员接口）
        cls.bank = ProblemBankCreateService().execute(
            ProblemBankCreateSchema(name="API Bank", slug="api-bank", is_public=True)
        )
        cls.bank_challenges = BankImportFromContestService().execute(
            BankImportFromContestSchema(bank_slug=cls.bank.slug, contest_slug=cls.contest.slug)
        )

    def setUp(self):
        self.bank_repo = ProblemBankRepo()
        self.challenge_repo = BankChallengeRepo()
        self.solve_repo = BankSolveRepo()
        # 避免 PermissionDeniedError 被测试客户端抛出，直接拿到 403 响应
        self.client.raise_request_exception = False

    def test_bank_flow(self):
        # 列表/详情（使用预置题库）
        player_client = self.auth_client("alice", "Passw0rd123")
        resp = player_client.get("/api/problem-bank/api-bank/")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.data["data"]["items"])
        resp = player_client.get("/api/problem-bank/api-bank/for-bank/")
        self.assertEqual(resp.status_code, 200, resp.content)
        # 作答
        resp = player_client.post(
            "/api/problem-bank/api-bank/for-bank/submit/",
            {"flag": "flag{demo}"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        # 已解标记
        resp = player_client.get("/api/problem-bank/api-bank/")
        solved_flags = [item["solved"] for item in resp.data["data"]["items"] if item["slug"] == "for-bank"]
        self.assertEqual(solved_flags, [True])

    def test_private_bank_forbidden_for_regular_user(self):
        """非公开题库应拒绝普通用户访问"""
        private_bank = ProblemBankCreateService().execute(
            ProblemBankCreateSchema(name="Private Bank", slug="private-bank", is_public=False)
        )
        BankChallenge.objects.create(
            bank=private_bank,
            category=None,
            title="Hidden",
            slug="hidden",
            content="secret",
            flag="secret",
            dynamic_prefix="flag",
        )
        player_client = self.auth_client("alice", "Passw0rd123")
        player_client.raise_request_exception = False
        resp = player_client.get("/api/problem-bank/private-bank/")
        self.assertEqual(resp.status_code, 403, resp.content)
        self.assertEqual(resp.data.get("code"), 40300)

    def test_inactive_challenge_not_listed(self):
        """下线的题库题目不应出现在列表中"""
        inactive_slug = "inactive-bank-challenge"
        BankChallenge.objects.create(
            bank=self.bank,
            category=None,
            title="Inactive Challenge",
            slug=inactive_slug,
            content="hidden",
            flag="demo",
            dynamic_prefix="flag",
            is_active=False,
        )
        player_client = self.auth_client("alice", "Passw0rd123")
        resp = player_client.get(f"/api/problem-bank/{self.bank.slug}/")
        self.assertEqual(resp.status_code, 200, resp.content)
        slugs = [item["slug"] for item in resp.data["data"]["items"]]
        self.assertNotIn(inactive_slug, slugs)

    def test_bank_list_search_fields(self):
        """题库列表搜索字段：题库名/题目名/题目类型"""
        player_client = self.auth_client("alice", "Passw0rd123")
        # 补充分类与标题，便于检索
        category = BankCategory.objects.create(bank=self.bank, name="Crypto", slug="crypto")
        challenge = self.bank_challenges[0]
        challenge.title = "Crypto Starter"
        challenge.category = category
        challenge.save()
        # 另一个题库，用于排除
        other_bank = ProblemBankCreateService().execute(
            ProblemBankCreateSchema(name="Other Bank", slug="other-bank", is_public=True)
        )
        BankChallenge.objects.create(
            bank=other_bank,
            category=None,
            title="Misc Title",
            slug="misc-title",
            short_description="desc",
            content="ct",
            difficulty=BankChallenge.Difficulty.MEDIUM,
            flag="flag",
            dynamic_prefix="FLAG",
            author=self.admin,
        )
        # 按题库名
        resp = player_client.get("/api/problem-bank/", {"bank_keyword": "API"})
        self.assertEqual(resp.status_code, 200, resp.content)
        names = [item["name"] for item in resp.data["data"]["items"]]
        self.assertIn("API Bank", names)
        # 按题目名
        resp = player_client.get("/api/problem-bank/", {"challenge_keyword": "Starter"})
        self.assertEqual(resp.status_code, 200, resp.content)
        names = [item["name"] for item in resp.data["data"]["items"]]
        self.assertIn("API Bank", names)
        self.assertNotIn("Other Bank", names)
        # 按题目类型（分类）
        resp = player_client.get("/api/problem-bank/", {"category_keyword": "crypto"})
        self.assertEqual(resp.status_code, 200, resp.content)
        names = [item["name"] for item in resp.data["data"]["items"]]
        self.assertIn("API Bank", names)
