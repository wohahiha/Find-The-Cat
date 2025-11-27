from __future__ import annotations

from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone
from django.conf import settings
from django.test import override_settings
from rest_framework.test import APITestCase
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import User, EmailVerificationCode
from apps.common.tests_utils import AuthenticatedAPIMixin
from apps.contests.models import Contest
from apps.contests.schemas import TeamCreateSchema
from apps.contests.services import TeamCreateService
from apps.common.exceptions import WrongFlagError, ChallengeAlreadySolvedError
from apps.common.exceptions import ValidationError

from .schemas import ChallengeCreateSchema
from .services import ChallengeCreateService
from .repo import ChallengeRepo
from apps.submissions.schemas import SubmissionCreateSchema
from apps.submissions.services import SubmissionService


# 测试用例：覆盖题目创建/提交的服务逻辑与 API 冒烟


class ChallengeServiceTests(TestCase):
    """
    服务层单测：
    - 验证创建题目成功路径
    - 验证静态/动态 Flag 判题、重复提交等业务分支
    """

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
        """创建题目后可通过仓储按 slug 获取"""
        schema = ChallengeCreateSchema(
            contest_slug="autumn-ctf",
            title="Warmup",
            slug="warmup",
            content="Find the flag",
            flag="demo",
            dynamic_prefix="flag",
            category="Misc",
        )
        challenge = ChallengeCreateService().execute(self.author, schema)
        self.assertEqual(challenge.title, "Warmup")
        repo = ChallengeRepo()
        fetched = repo.get_by_slug(contest=self.contest, slug="warmup")
        self.assertEqual(fetched.title, "Warmup")

    def test_challenge_submit_success(self):
        """成功提交正确 Flag，生成解题记录"""
        ChallengeCreateService().execute(
            self.author,
            ChallengeCreateSchema(
                contest_slug="autumn-ctf",
                title="Warmup",
                slug="warmup",
                content="Find the flag",
                flag="demo",
                dynamic_prefix="flag",
                category="Misc",
            ),
        )
        TeamCreateService().execute(
            self.player,
            TeamCreateSchema(contest_slug="autumn-ctf", name="Solo"),
        )
        schema = SubmissionCreateSchema(contest_slug="autumn-ctf", challenge_slug="warmup", flag="flag{demo}")
        submission = SubmissionService().execute(self.player, schema)
        self.assertEqual(submission.user, self.player)
        self.assertEqual(submission.challenge.slug, "warmup")
        self.assertIsNotNone(submission.solve)

    def test_flag_schema_validation(self):
        """Flag 校验：静态需 flag，前缀不能含花括号，动态需种子"""
        with self.assertRaises(ValidationError):
            ChallengeCreateSchema(
                contest_slug="autumn-ctf",
                title="NoFlag",
                slug="noflag",
                content="empty",
                flag="",
            ).validate()
        with self.assertRaises(ValidationError):
            ChallengeCreateSchema(
                contest_slug="autumn-ctf",
                title="StaticWithPrefix",
                slug="static-prefix",
                content="xx",
                flag="demo",
                flag_type="static",
                dynamic_prefix="flag{",
            ).validate()
        with self.assertRaises(ValidationError):
            ChallengeCreateSchema(
                contest_slug="autumn-ctf",
                title="DynNoSeed",
                slug="dyn-no-seed",
                content="xx",
                flag="",
                flag_type="dynamic",
            ).validate()

    def test_dynamic_flag_generation_and_check(self):
        """动态 Flag：按用户生成唯一 Flag，正确通过，错误/重复抛业务异常"""
        challenge = ChallengeCreateService().execute(
            self.author,
            ChallengeCreateSchema(
                contest_slug="autumn-ctf",
                title="DynFlag",
                slug="dyn-flag",
                content="动态 flag 测试",
                flag="secret-seed",
                flag_type="dynamic",
                dynamic_prefix="flag",
            ),
        )
        expected_flag = self._build_expected_flag(challenge, self.player)
        # 正确 flag 提交通过
        submission = SubmissionService().execute(
            self.player,
            SubmissionCreateSchema(contest_slug="autumn-ctf", challenge_slug="dyn-flag", flag=expected_flag),
        )
        self.assertEqual(submission.challenge_id, challenge.id)
        self.assertIsNotNone(submission.solve)
        # 已解出后再次提交应提示重复
        with self.assertRaises(ChallengeAlreadySolvedError):
            SubmissionService().execute(
                self.player,
                SubmissionCreateSchema(contest_slug="autumn-ctf", challenge_slug="dyn-flag", flag="flag{wrong}"),
            )

    def _build_expected_flag(self, challenge, user):
        """按照服务端逻辑构造动态 Flag，供断言使用"""
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
class ChallengesAPITestCase(AuthenticatedAPIMixin, APITestCase):
    """挑战模块接口冒烟：题目 CRUD、提交/动态 Flag、附件上传"""

    @classmethod
    def setUpTestData(cls):
        cache.clear()
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

    def setUp(self):
        cache.clear()

    def test_challenge_crud_and_submit(self):
        """接口链路冒烟：创建题目、列表/详情查看、提交 Flag 与重复提交校验"""
        admin_client = self._auth_client("wohahiha", "stevenxu5190")
        player_client = self._auth_client("alice", "Passw0rd123")

        # 创建题目（含子任务/附件）
        resp = admin_client.post(
            f"/api/contests/{self.contest.slug}/challenges/",
            {
                "title": "Warmup",
                "slug": "warmup",
                "content": "Find flag",
                "flag": "demo",
                "dynamic_prefix": "flag",
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
        self.assertIn("current_points", resp.data["data"]["items"][0])

        # 详情
        resp = player_client.get(f"/api/contests/{self.contest.slug}/challenges/warmup/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("tasks", resp.data["data"]["challenge"])
        self.assertIn("current_points", resp.data["data"]["challenge"])

        # 提交正确 Flag（统一使用 submissions 接口）
        resp = player_client.post(
            "/api/submissions/",
            {"contest_slug": self.contest.slug, "challenge_slug": "warmup", "flag": "flag{demo}"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(
            resp.data["data"]["challenge"]["current_points"],
            resp.data["data"]["awarded_points"],
        )
        # 重复提交应返回业务错误
        resp = player_client.post(
            "/api/submissions/",
            {"contest_slug": self.contest.slug, "challenge_slug": "warmup", "flag": "flag{demo}"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_dynamic_flag_submit_api(self):
        """接口层动态 Flag：按用户生成唯一值，正确通过，错误返回业务错误"""
        admin_client = self._auth_client("wohahiha", "stevenxu5190")
        player_client = self._auth_client("alice", "Passw0rd123")

        # 创建动态 Flag 题目
        resp = admin_client.post(
            f"/api/contests/{self.contest.slug}/challenges/",
            {
                "title": "DynAPI",
                "slug": "dyn-api",
                "content": "动态 flag API 测试",
                "flag": "seed-api",
                "flag_type": "dynamic",
                "dynamic_prefix": "flag",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        challenge = ChallengeRepo().get_by_slug(contest=self.contest, slug="dyn-api")

        expected_flag = self._build_dynamic_flag(challenge, self.player)
        ok_resp = player_client.post(
            "/api/submissions/",
            {"contest_slug": self.contest.slug, "challenge_slug": "dyn-api", "flag": expected_flag},
            format="json",
        )
        self.assertEqual(ok_resp.status_code, 201)

        bad_resp = player_client.post(
            "/api/submissions/",
            {"contest_slug": self.contest.slug, "challenge_slug": "dyn-api", "flag": "flag{wrong}"},
            format="json",
        )
        self.assertEqual(bad_resp.status_code, 400)

    def test_attachment_upload_api(self):
        """管理员上传附件，返回路径与 URL"""
        admin_client = self._auth_client("wohahiha", "stevenxu5190")
        file = SimpleUploadedFile("readme.txt", b"hello", content_type="text/plain")
        resp = admin_client.post(
            f"/api/contests/{self.contest.slug}/challenges/attachments/upload/",
            {"file": file, "contest_slug": self.contest.slug, "challenge_slug": "warmup"},
            format="multipart",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIn("attachment", resp.data["data"])

    def _build_dynamic_flag(self, challenge, user):
        """复用服务端规则构造动态 Flag，便于接口断言"""
        return challenge.build_expected_flag(user=user, secret=settings.SECRET_KEY)
