from __future__ import annotations

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
        "DEFAULT_AUTHENTICATION_CLASSES": ("apps.common.authentication.JWTAuthentication",),
        "DEFAULT_PERMISSION_CLASSES": ("apps.common.permissions.IsAuthenticated",),
        "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    },
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
