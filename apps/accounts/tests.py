from __future__ import annotations

from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone
from django.conf import settings
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import User, EmailVerificationCode
from apps.common.tests_utils import AuthenticatedAPIMixin


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
class AccountsAPITestCase(AuthenticatedAPIMixin, APITestCase):
    """
    账户模块接口冒烟测试：
    - 覆盖注册、登录、重置密码、资料修改、改密/改邮、注销的主干链路。
    - 继承 AuthenticatedAPIMixin，提供快捷登录与认证客户端工具。
    - 提高节流阈值，避免测试过程触发限流。
    """

    @classmethod
    def setUpTestData(cls):
        # 创建管理员（用于后续可能的管理操作）
        cls.admin = User.objects.create_superuser(
            username="wohahiha",
            email="admin@example.com",
            password="stevenxu5190",
        )
        # 创建普通用户
        cls.user = User.objects.create_user(
            username="tester",
            email="tester@example.com",
            password="Passw0rd123",
        )

    def setUp(self):
        # 清理 throttle 缓存，避免跨用例触发限流
        cache.clear()

    def make_email_code(self, email: str, scene: str, code: str = "123456") -> EmailVerificationCode:
        """造一个未过期的邮箱验证码记录，便于模拟验证码通过。"""
        return EmailVerificationCode.objects.create(
            email=email,
            scene=scene,
            code=code,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

    def test_send_email_verification(self):
        """发送验证码接口应成功返回 sent 标志。"""
        resp = self.client.post(
            "/api/accounts/email/verification/",
            {"email": "newuser@example.com", "scene": EmailVerificationCode.Scene.REGISTER},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data["data"]["sent"])

    def test_register_and_login(self):
        """注册成功后可用新账号登录。"""
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

    def test_password_reset_flow(self):
        """重置密码流程：申请验证码→消费验证码→新密码可用。"""
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
        """获取并更新个人资料，昵称应被修改。"""
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
        """修改密码后，应可用新密码登录。"""
        client = self.auth_client(self.user.username, "Passw0rd123")
        resp = client.post(
            "/api/accounts/auth/password/change/",
            {
                "old_password": "Passw0rd123",
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
        """变更邮箱后，返回的新邮箱应为预期值。"""
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

    def test_delete_account(self):
        """注销账户应禁用账号，字段被软删除处理。"""
        client = self.auth_client(self.user.username, "Passw0rd123")
        resp = client.post(
            "/api/accounts/me/deactivate/",
            {"password": "Passw0rd123"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
