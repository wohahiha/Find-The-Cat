from __future__ import annotations

from django.test import TestCase, override_settings
from django.conf import settings
from django.core.cache import cache
from rest_framework.test import APITestCase
from datetime import timedelta
from django.utils import timezone

from apps.accounts.models import User
from apps.contests.models import Contest
from apps.contests.schemas import TeamCreateSchema
from apps.contests.services import TeamCreateService, ContestRegisterService
from apps.challenges.schemas import ChallengeCreateSchema
from apps.challenges.services import ChallengeCreateService
from apps.challenges.repo import ChallengeRepo
from apps.submissions.models import Submission
from apps.common.tests_utils import AuthenticatedAPIMixin
from apps.common.exceptions import ValidationError
from apps.contests.repo import TeamRepo, TeamMemberRepo
from apps.contests.models import TeamMember
from apps.common.security import get_flag_secret

from .schemas import SubmissionCreateSchema
from .services import SubmissionService
from apps.common.infra import redis_client
from apps.common.utils.redis_keys import blood_rank_key


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "submissions-service-tests",
        }
    }
)
class SubmissionServiceTests(TestCase):
    """服务层单测：校验提交记录、判题与重复提交行为"""

    def setUp(self) -> None:
        """准备进行中的比赛、用户与题目，供提交测试使用"""
        now = timezone.now()
        self.contest = Contest.objects.create(
            name="Submit CTF",
            slug="submit-ctf",
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=5),
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
        # 组队赛：确保存在队伍与成员关系以通过提交校验
        self.team_repo = TeamRepo()
        self.member_repo = TeamMemberRepo()
        self.team = self.team_repo.create_team(contest=self.contest, captain=self.user, name="solo-team")
        self.member_repo.create_member(team=self.team, user=self.user, role=TeamMember.Role.CAPTAIN)
        # 清理血次序缓存，避免跨用例污染
        warmup = ChallengeRepo().get_by_slug(contest=self.contest, slug="warmup")
        redis_client.delete(blood_rank_key(getattr(warmup, "id", None)))

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

    def test_wrong_flag_stores_original_payload(self):
        """错误提交应落库原始 Flag，得分为 0、额外加分为 0"""
        flag_value = "flag{totally-wrong}"
        schema = SubmissionCreateSchema(contest_slug="submit-ctf", challenge_slug="warmup", flag=flag_value)
        with self.assertRaises(Exception):
            SubmissionService().execute(self.user, schema)
        submission = Submission.objects.latest("created_at")
        self.assertEqual(submission.flag_submitted, flag_value)
        self.assertEqual(submission.awarded_points, 0)
        self.assertEqual(submission.bonus_points, 0)

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
        dyn_challenge = ChallengeRepo().get_by_slug(contest=self.contest, slug="dyn")
        redis_client.delete(blood_rank_key(getattr(dyn_challenge, "id", None)))
        # 按动态规则构造 flag 提交
        expected_flag = self._build_dynamic_flag(self.contest, "dyn", self.user)
        submission = SubmissionService().execute(
            self.user,
            SubmissionCreateSchema(contest_slug="submit-ctf", challenge_slug="dyn", flag=expected_flag),
        )
        self.assertTrue(submission.is_correct)
        self.assertEqual(submission.flag_submitted, expected_flag)
        self.assertEqual(submission.blood_rank, 1)

    def test_team_based_submission_without_membership_is_rejected(self):
        """团队赛未入队的选手提交应被拒绝"""
        now = timezone.now()
        contest = Contest.objects.create(
            name="Team Only",
            slug="team-only",
            start_time=now - timedelta(minutes=30),
            end_time=now + timedelta(hours=2),
            is_team_based=True,
        )
        ChallengeCreateService().execute(
            self.user,
            ChallengeCreateSchema(
                contest_slug=contest.slug,
                title="Team Warmup",
                slug="team-warmup",
                content="Find flag",
                flag="demo",
                dynamic_prefix="flag",
            ),
        )
        schema = SubmissionCreateSchema(contest_slug=contest.slug, challenge_slug="team-warmup", flag="flag{demo}")
        with self.assertRaises(ValidationError):
            SubmissionService().execute(self.user, schema)

    def test_submission_before_contest_start_is_rejected(self):
        """未开赛时的提交应被比赛状态校验拒绝"""
        now = timezone.now()
        contest = Contest.objects.create(
            name="Future Contest",
            slug="future-contest",
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            is_team_based=False,
        )
        ChallengeCreateService().execute(
            self.user,
            ChallengeCreateSchema(
                contest_slug=contest.slug,
                title="FutureWarmup",
                slug="future-warmup",
                content="wait",
                flag="demo",
                dynamic_prefix="flag",
            ),
        )
        schema = SubmissionCreateSchema(contest_slug=contest.slug, challenge_slug="future-warmup", flag="flag{demo}")
        with self.assertRaises(ValidationError):
            SubmissionService().execute(self.user, schema)

    @staticmethod
    def _build_dynamic_flag(contest, challenge_slug: str, user):
        challenge = ChallengeRepo().get_by_slug(contest=contest, slug=challenge_slug)
        membership = TeamMemberRepo().get_membership(contest=contest, user=user)
        return challenge.build_expected_flag(user=user, membership=membership, secret=get_flag_secret())  # type: ignore[attr-defined]


@override_settings(
    REST_FRAMEWORK={
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_RATES": {
            **settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {}),
            "login": "1000/min",
            "user_post": "1000/min",
        },
    },
    ALLOW_LOGIN_WITHOUT_CAPTCHA=True,
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "submissions-tests",
        }
    },
)
class SubmissionsAPITestCase(AuthenticatedAPIMixin, APITestCase):
    """Submissions 接口冒烟：提交正确/错误及重复行为"""

    @classmethod
    def setUpTestData(cls):
        """一次性创建用户、管理员、比赛与题目，供接口测试复用"""
        cls.user = User.objects.create_user(username="alice", email="alice@example.com", password="Passw0rd123")
        cls.user.is_email_verified = True
        cls.user.save()
        cls.admin = User.objects.create_superuser(username="admin_test_user", email="admin@example.com",
                                                  password="StrongPass123!")
        cls.admin.is_email_verified = True
        cls.admin.save()
        now = timezone.now()
        cls.contest = Contest.objects.create(
            name="API Submit",
            slug="api-submit",
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=3),
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
        ContestRegisterService().execute(cls.user, "api-submit")
        TeamCreateService().execute(cls.user, TeamCreateSchema(contest_slug="api-submit", name="Solo"))
        # 组队与报名在开赛前完成，随后调整为进行中便于接口测试
        cls.contest.start_time = now - timedelta(minutes=30)
        cls.contest.end_time = now + timedelta(hours=2)
        cls.contest.save(update_fields=["start_time", "end_time"])

    def setUp(self):
        """每个测试前清理缓存，避免节流或残留数据影响"""
        cache.clear()

    def test_submit_api_correct_and_wrong(self):
        client = self._auth_client("alice", "Passw0rd123")
        # 正确提交
        resp = client.post(
            f"/api/contests/{self.contest.slug}/submissions/",
            {"contest_slug": "api-submit", "challenge_slug": "warmup", "flag": "flag{demo}"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        # 错误提交，记录但返回错误
        resp = client.post(
            f"/api/contests/{self.contest.slug}/submissions/",
            {"contest_slug": "api-submit", "challenge_slug": "warmup", "flag": "flag{wrong}"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        # 查看个人提交列表
        list_resp = client.get(f"/api/contests/{self.contest.slug}/submissions/?scope=personal")
        self.assertEqual(list_resp.status_code, 200, list_resp.content)
        # 返回分页结构，结果在 results/items
        items = list_resp.data["data"].get("results") or list_resp.data["data"].get("items")
        self.assertTrue(items)

    def test_dynamic_submit_api(self):
        admin_client = self._auth_client("admin_test_user", "StrongPass123!")
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
            f"/api/contests/{self.contest.slug}/submissions/",
            {"contest_slug": self.contest.slug, "challenge_slug": "dyn", "flag": dyn_flag},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)

    def test_duplicate_submit(self):
        client = self._auth_client("alice", "Passw0rd123")
        resp = client.post(
            f"/api/contests/{self.contest.slug}/submissions/",
            {"contest_slug": "api-submit", "challenge_slug": "warmup", "flag": "flag{demo}"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        # 重复提交
        resp = client.post(
            f"/api/contests/{self.contest.slug}/submissions/",
            {"contest_slug": "api-submit", "challenge_slug": "warmup", "flag": "flag{demo}"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    @staticmethod
    def _build_dynamic_flag(_contest, challenge, user):
        membership = TeamMemberRepo().get_membership(contest=_contest, user=user)
        return challenge.build_expected_flag(user=user, membership=membership, secret=get_flag_secret())  # type: ignore[attr-defined]
