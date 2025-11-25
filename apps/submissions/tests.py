from __future__ import annotations

from django.test import TestCase, override_settings
from django.conf import settings
from django.core.cache import cache
from rest_framework.test import APITestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.contests.models import Contest
from apps.contests.schemas import TeamCreateSchema
from apps.contests.services import TeamCreateService
from apps.challenges.schemas import ChallengeCreateSchema
from apps.challenges.services import ChallengeCreateService
from apps.challenges.repo import ChallengeRepo
from apps.submissions.models import Submission
from apps.common.tests_utils import AuthenticatedAPIMixin

from .schemas import SubmissionCreateSchema
from .services import SubmissionService


class SubmissionServiceTests(TestCase):
    """服务层单测：校验提交记录、判题与重复提交行为。"""

    def setUp(self) -> None:
        """准备进行中的比赛、用户与题目，供提交测试使用。"""
        now = timezone.now()
        self.contest = Contest.objects.create(
            name="Submit CTF",
            slug="submit-ctf",
            start_time=now - timezone.timedelta(hours=1),
            end_time=now + timezone.timedelta(hours=5),
        )
        self.user = User.objects.create_user(username="player", email="p@example.com", password="Pass1234")
        ChallengeCreateService().execute(
            self.user,
            ChallengeCreateSchema(
                contest_slug="submit-ctf",
                title="Warmup",
                slug="warmup",
                content="Find flag",
                flag="demo",
                dynamic_prefix="flag",
            ),
        )

    def test_submit_correct_creates_solve(self):
        schema = SubmissionCreateSchema(contest_slug="submit-ctf", challenge_slug="warmup", flag="flag{demo}")
        submission = SubmissionService().execute(self.user, schema)
        self.assertTrue(submission.is_correct)
        self.assertEqual(submission.status, Submission.Status.ACCEPTED)
        self.assertIsNotNone(submission.solve)

    def test_submit_wrong_records_and_raises(self):
        schema = SubmissionCreateSchema(contest_slug="submit-ctf", challenge_slug="warmup", flag="flag{wrong}")
        with self.assertRaises(Exception):
            SubmissionService().execute(self.user, schema)
        self.assertEqual(Submission.objects.count(), 1)
        submission = Submission.objects.first()
        assert submission is not None
        self.assertFalse(submission.is_correct)
        self.assertEqual(submission.status, Submission.Status.REJECTED)

    def test_dynamic_flag_needs_machine(self):
        ChallengeCreateService().execute(
            self.user,
            ChallengeCreateSchema(
                contest_slug="submit-ctf",
                title="Dynamic",
                slug="dyn",
                content="dyn flag",
                flag="placeholder",
                flag_type="dynamic",
                dynamic_prefix="flag",
            ),
        )
        # 按动态规则构造 flag 提交
        expected_flag = self._build_dynamic_flag(self.contest, "dyn", self.user)
        submission = SubmissionService().execute(
            self.user,
            SubmissionCreateSchema(contest_slug="submit-ctf", challenge_slug="dyn", flag=expected_flag),
        )
        self.assertTrue(submission.is_correct)
        self.assertEqual(submission.flag_submitted, expected_flag)
        self.assertEqual(submission.blood_rank, 1)

    def _build_dynamic_flag(self, contest, challenge_slug: str, user):
        challenge = ChallengeRepo().get_by_slug(contest=contest, slug=challenge_slug)
        return challenge.build_expected_flag(user=user, secret=settings.SECRET_KEY)


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
class SubmissionsAPITestCase(AuthenticatedAPIMixin, APITestCase):
    """Submissions 接口冒烟：提交正确/错误及重复行为。"""

    @classmethod
    def setUpTestData(cls):
        """一次性创建用户、管理员、比赛与题目，供接口测试复用。"""
        cls.user = User.objects.create_user(username="alice", email="alice@example.com", password="Passw0rd123")
        cls.admin = User.objects.create_superuser(username="wohahiha", email="admin@example.com", password="stevenxu5190")
        now = timezone.now()
        cls.contest = Contest.objects.create(
            name="API Submit",
            slug="api-submit",
            start_time=now - timezone.timedelta(hours=1),
            end_time=now + timezone.timedelta(hours=1),
        )
        ChallengeCreateService().execute(
            cls.admin,
            ChallengeCreateSchema(
                contest_slug="api-submit",
                title="Warmup",
                slug="warmup",
                content="Find flag",
                flag="demo",
                dynamic_prefix="flag",
            ),
        )
        TeamCreateService().execute(cls.user, TeamCreateSchema(contest_slug="api-submit", name="Solo"))

    def setUp(self):
        """每个测试前清理缓存，避免节流或残留数据影响。"""
        cache.clear()

    def test_submit_api_correct_and_wrong(self):
        client = self._auth_client("alice", "Passw0rd123")
        # 正确提交
        resp = client.post(
            "/api/submissions/",
            {"contest_slug": "api-submit", "challenge_slug": "warmup", "flag": "flag{demo}"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        # 错误提交，记录但返回错误
        resp = client.post(
            "/api/submissions/",
            {"contest_slug": "api-submit", "challenge_slug": "warmup", "flag": "flag{wrong}"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_dynamic_submit_api(self):
        admin_client = self._auth_client("wohahiha", "stevenxu5190")
        # 创建动态题目
        resp = admin_client.post(
            f"/api/contests/{self.contest.slug}/challenges/",
            {
                "title": "Dyn",
                "slug": "dyn",
                "content": "dyn",
                "flag": "placeholder",
                "flag_type": "dynamic",
                "dynamic_prefix": "flag",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        player_client = self._auth_client("alice", "Passw0rd123")
        # 直接按动态规则提交
        challenge = ChallengeRepo().get_by_slug(contest=self.contest, slug="dyn")
        dyn_flag = self._build_dynamic_flag(self.contest, challenge, self.user)
        resp = player_client.post(
            "/api/submissions/",
            {"contest_slug": self.contest.slug, "challenge_slug": "dyn", "flag": dyn_flag},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)

    def test_duplicate_submit(self):
        client = self._auth_client("alice", "Passw0rd123")
        resp = client.post(
            "/api/submissions/",
            {"contest_slug": "api-submit", "challenge_slug": "warmup", "flag": "flag{demo}"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        # 重复提交
        resp = client.post(
            "/api/submissions/",
            {"contest_slug": "api-submit", "challenge_slug": "warmup", "flag": "flag{demo}"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def _build_dynamic_flag(self, contest, challenge, user):
        return challenge.build_expected_flag(user=user, membership=None, secret=settings.SECRET_KEY)
