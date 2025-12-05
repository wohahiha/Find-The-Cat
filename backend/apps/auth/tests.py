# -*- coding: utf-8 -*-
"""
认证与权限模块测试占位
"""

from django.apps import apps
from django.test import TestCase


class AuthAppSmokeTest(TestCase):
    """
    确认应用已注册且可加载
    """

    def test_app_installed(self):
        """
        确认 AuthConfig 已在 INSTALLED_APPS 中注册
        """
        self.assertTrue(apps.is_installed("apps.auth"))
