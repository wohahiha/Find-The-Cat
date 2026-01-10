from __future__ import annotations

from datetime import timedelta
import base64
import tempfile

from django.core.cache import cache
from django.utils import timezone
from django.conf import settings
from django.test import override_settings
from rest_framework.test import APITestCase
from django.core.files.uploadedfile import SimpleUploadedFile

# EmailVerificationCode 已迁移至 system 模块
from apps.system.models import EmailVerificationCode
from apps.accounts.models import User
from apps.accounts.services import SendEmailVerificationService
from apps.common.tests_utils import AuthenticatedAPIMixin


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
            "LOCATION": "accounts-tests",
        }
    },
    ALLOW_LOGIN_WITHOUT_CAPTCHA=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class AccountsAPITestCase(AuthenticatedAPIMixin, APITestCase):
    """
    账户模块接口冒烟测试：
    - 覆盖注册、登录、重置密码、资料修改、改密/改邮、注销的主干链路
    - 继承 AuthenticatedAPIMixin，提供快捷登录与认证客户端工具
    - 提高节流阈值，避免测试过程触发限流
    """

    @classmethod
    def setUpClass(cls):
        """测试环境跳过实际邮件发送，避免依赖外部 SMTP/MailAccount"""
        super().setUpClass()
        cls._orig_deliver = SendEmailVerificationService._deliver
        SendEmailVerificationService._deliver = lambda self, email, scene, code: None

    @classmethod
    def tearDownClass(cls):
        SendEmailVerificationService._deliver = cls._orig_deliver
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        # 创建管理员（用于后续可能的管理操作）
        cls.admin = User.objects.create_superuser(
            username="admin_test_user",
            email="admin@example.com",
            password="StrongPass123!",
        )
        cls.admin.is_email_verified = True
        cls.admin.save()
        # 创建普通用户
        cls.user = User.objects.create_user(
            username="tester",
            email="tester@example.com",
            password="Passw0rd123",
        )
        cls.user.is_email_verified = True
        cls.user.save()

    def setUp(self):
        # 清理 throttle 缓存，避免跨用例触发限流
        cache.clear()

    @staticmethod
    def make_email_code(email: str, scene: str, code: str = "123456") -> EmailVerificationCode:
        """造一个未过期的邮箱验证码记录，便于模拟验证码通过"""
        return EmailVerificationCode.objects.create(
            email=email,
            scene=scene,
            code=code,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

    def test_send_email_verification(self):
        """发送验证码接口应成功返回 sent 标志"""
        resp = self.client.post(
            "/api/accounts/email/verification/",
            {"email": "newuser@example.com", "scene": EmailVerificationCode.Scene.REGISTER},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["data"]["sent"])  # type: ignore[index]

    def test_register_and_login(self):
        """注册成功后可用新账号登录"""
        email = "reg@example.com"
        self.make_email_code(email, EmailVerificationCode.Scene.REGISTER, code="111111")
        resp = self.client.post(
            "/api/accounts/auth/register/",
            {
                "username": "reguser",
                "email": email,
                "password": "Passw0rd123",
                "confirm_password": "Passw0rd123",
                "email_code": "111111",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        # 登录验证
        token = self.api_login("reguser", "Passw0rd123")
        self.assertTrue(token)

    def test_register_with_duplicate_email_should_fail(self):
        """重复邮箱注册应返回业务错误，状态码 400"""
        email = self.user.email
        self.make_email_code(email, EmailVerificationCode.Scene.REGISTER, code="111112")
        resp = self.client.post(
            "/api/accounts/auth/register/",
            {
                "username": "dupuser",
                "email": email,
                "password": "Passw0rd123",
                "confirm_password": "Passw0rd123",
                "email_code": "111112",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 409)
        self.assertNotEqual(resp.data.get("code"), 0)  # type: ignore[call-arg]

    def test_password_reset_flow(self):
        """重置密码流程：申请验证码→消费验证码→新密码可用"""
        email = self.user.email
        # 申请验证码
        resp = self.client.post(
            "/api/accounts/auth/password/reset/request/",
            {"email": email},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        # 直接造一条验证码用于重置
        self.make_email_code(email, EmailVerificationCode.Scene.RESET_PASSWORD, code="222222")
        resp = self.client.post(
            "/api/accounts/auth/password/reset/",
            {
                "email": email,
                "code": "222222",
                "new_password": "NewPassw0rd123",
                "confirm_password": "NewPassw0rd123",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        # 新密码可用
        token = self.api_login(email, "NewPassw0rd123")
        self.assertTrue(token)

    def test_profile_get_and_update(self):
        """获取并更新个人资料，昵称应被修改"""
        client = self.auth_client(self.user.username, "Passw0rd123")
        resp = client.get("/api/accounts/me/")
        self.assertEqual(resp.status_code, 200)
        resp = client.patch(
            "/api/accounts/me/",
            {"nickname": "New Nick"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["data"]["user"]["nickname"], "New Nick")

    def test_change_password(self):
        """修改密码后，应可用新密码登录"""
        client = self.auth_client(self.user.username, "Passw0rd123")
        # 预生成修改密码场景的邮箱验证码
        self.make_email_code(self.user.email, EmailVerificationCode.Scene.CHANGE_PASSWORD, code="444444")
        resp = client.post(
            "/api/accounts/auth/password/change/",
            {
                "old_password": "Passw0rd123",
                "email_code": "444444",
                "new_password": "AnotherPassw0rd123",
                "confirm_password": "AnotherPassw0rd123",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        # 新密码生效
        token = self.api_login(self.user.username, "AnotherPassw0rd123")
        self.assertTrue(token)

    def test_change_email(self):
        """变更邮箱后，返回的新邮箱应为预期值"""
        client = self.auth_client(self.user.username, "Passw0rd123")
        new_email = "changed@example.com"
        self.make_email_code(new_email, EmailVerificationCode.Scene.BIND_EMAIL, code="333333")
        resp = client.post(
            "/api/accounts/email/change/",
            {
                "new_email": new_email,
                "email_code": "333333",
                "current_password": "Passw0rd123",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["data"]["user"]["email"], new_email)

    def test_profile_reject_html(self):
        """资料更新不应允许 HTML，防止 XSS"""
        client = self.auth_client(self.user.username, "Passw0rd123")
        resp = client.patch(
            "/api/accounts/me/",
            {"nickname": "<script>alert(1)</script>"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_avatar_upload(self):
        """上传头像应成功返回头像 URL 并写入用户记录"""
        client = self.auth_client(self.user.username, "Passw0rd123")
        png_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9YlT6y8AAAAASUVORK5CYII="
        avatar_bytes = base64.b64decode(png_base64)
        tmpdir = tempfile.mkdtemp()
        try:
            with override_settings(MEDIA_ROOT=tmpdir, MEDIA_URL="/media/"):
                file = SimpleUploadedFile("avatar.png", avatar_bytes, content_type="image/png")
                resp = client.post(
                    "/api/accounts/me/avatar/",
                    {"avatar": file},
                    format="multipart",
                )
                self.assertEqual(resp.status_code, 200)
                # 响应应包含头像 URL
                self.assertTrue(resp.data["data"]["avatar"])  # type: ignore[index]
                self.user.refresh_from_db()
                self.assertTrue(self.user.avatar)
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    @override_settings(
        REST_FRAMEWORK={
            **settings.REST_FRAMEWORK,
            "DEFAULT_THROTTLE_RATES": {
                **settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {}),
                "email_code_send": "1/min",
                "login": "1000/min",
                "user_post": "1000/min",
            },
        },
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "accounts-tests-throttle",
            }
        },
    )
    def test_email_code_send_throttle(self):
        """验证码发送触发限流应返回 429"""
        cache.clear()
        payload = {"email": "throttle@example.com", "scene": EmailVerificationCode.Scene.REGISTER}
        resp1 = self.client.post("/api/accounts/email/verification/", payload, format="json")
        self.assertEqual(resp1.status_code, 200)
        resp2 = self.client.post("/api/accounts/email/verification/", payload, format="json")
        self.assertEqual(resp2.status_code, 429)

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
                "LOCATION": "accounts-tests-codefail",
            }
        },
    )
    def test_email_code_fail_lock(self):
        """验证码连续错误应被封禁"""
        cache.clear()
        email = "lock@example.com"
        # 先发送验证码，生成记录
        self.client.post(
            "/api/accounts/email/verification/",
            {"email": email, "scene": EmailVerificationCode.Scene.REGISTER},
            format="json",
        )
        # 连续 5 次错误验证码
        for i in range(4):
            resp = self.client.post(
                "/api/accounts/auth/password/reset/",
                {
                    "email": email,
                    "code": "000000",
                    "new_password": "NewPassw0rd123",
                    "confirm_password": "NewPassw0rd123",
                },
                format="json",
            )
            self.assertIn(resp.status_code, (400, 429))
        resp_final = self.client.post(
            "/api/accounts/auth/password/reset/",
            {
                "email": email,
                "code": "000000",
                "new_password": "NewPassw0rd123",
                "confirm_password": "NewPassw0rd123",
            },
            format="json",
        )
        self.assertEqual(resp_final.status_code, 429)

    @override_settings(
        DEBUG=False,
        ALLOW_LOGIN_WITHOUT_CAPTCHA=False,
        REST_FRAMEWORK={
            **settings.REST_FRAMEWORK,
            "DEFAULT_THROTTLE_RATES": {
                **settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {}),
                "login": "1000/min",
            },
        },
    )
    def test_login_requires_captcha_in_prod(self):
        """生产模式应强制图形验证码"""
        resp = self.client.post(
            "/api/accounts/auth/login/",
            {"identifier": self.user.username, "password": "Passw0rd123"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_delete_account(self):
        """注销账户应禁用账号，字段被软删除处理"""
        client = self.auth_client(self.user.username, "Passw0rd123")
        resp = client.post(
            "/api/accounts/me/deactivate/",
            {"password": "Passw0rd123"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_login_wrong_password_should_fail(self):
        """使用错误密码登录应返回业务错误，状态码为 400"""
        resp = self.client.post(
            "/api/accounts/auth/login/",
            {"identifier": self.user.username, "password": "wrong-pass"},
            format="json",
        )
        self.assertEqual(resp.status_code, 401)
        # 业务 code 应非 0，提示信息应存在
        self.assertNotEqual(resp.data.get("code"), 0)  # type: ignore[call-arg]
        self.assertTrue(resp.data.get("message"))  # type: ignore[call-arg]

    def test_login_response_no_cookie(self):
        """登录响应不应写入 JWT Cookie（已关闭 Cookie 模式）"""
        resp = self.client.post(
            "/api/accounts/auth/login/",
            {"identifier": self.user.username, "password": "Passw0rd123"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        # 检查 Set-Cookie 头中不包含 jwt_token_in_cookie
        set_cookie = resp.headers.get("Set-Cookie", "")
        self.assertNotIn("jwt_token_in_cookie", set_cookie)

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
                "LOCATION": "accounts-login-lock",
            }
        },
    )
    def test_login_fail_lockout(self):
        """连续登录失败应被临时封禁"""
        cache.clear()
        for _ in range(5):
            self.client.post(
                "/api/accounts/auth/login/",
                {"identifier": self.user.username, "password": "wrong-pass"},
                format="json",
            )
        resp = self.client.post(
            "/api/accounts/auth/login/",
            {"identifier": self.user.username, "password": "wrong-pass"},
            format="json",
        )
        self.assertEqual(resp.status_code, 429)
