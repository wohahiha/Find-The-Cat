from __future__ import annotations

from typing import Any

from rest_framework.test import APIClient


class AuthenticatedAPIMixin:
    """
    提供统一的登录与认证客户端构造工具，减少各测试用例的重复代码。
    """

    login_url: str = "/api/accounts/auth/login/"

    def api_login(self, identifier: str, password: str, expect_status: int = 200) -> str:
        """
        登录并返回访问令牌，默认期望 200 状态。
        """
        resp = self.client.post(
            self.login_url,
            {"identifier": identifier, "password": password},
            format="json",
        )
        self.assertEqual(resp.status_code, expect_status)
        return resp.data["data"]["access"]

    def auth_client(self, identifier: str, password: str) -> APIClient:
        """
        构造附带 Authorization 头的 APIClient。
        """
        token = self.api_login(identifier, password)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return client

    # 兼容已有命名
    def _login(self, identifier: str, password: str) -> str:
        return self.api_login(identifier, password)

    def _auth_client(self, identifier: str, password: str) -> APIClient:
        return self.auth_client(identifier, password)
