# -*- coding: utf-8 -*-
"""
系统配置与安全校验单测
- 验证 MailAccountAdmin 对 Logo 上传的类型/大小限制
"""
from __future__ import annotations

from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.admin.sites import AdminSite

from apps.system.admin import MailAccountAdmin
from apps.system.models import MailAccount


class DummyRequest:
    pass


class MailAccountAdminFormTests(TestCase):
    """验证 MailAccountAdmin 表单的安全校验（Logo 上传限制）"""

    def setUp(self):
        self.site = AdminSite()
        self.admin = MailAccountAdmin(MailAccount, self.site)

    def test_logo_invalid_type_should_fail(self):
        form_class = self.admin.get_form(DummyRequest())
        form = form_class(
            data={
                "name": "test",
                "provider": MailAccount.Provider.CUSTOM,
                "username": "a@example.com",
                "password": "pwd",
                "host": "smtp.example.com",
                "port": 587,
                "connection_security": "tls",
                "verification_expire_minutes": 10,
            },
            files={
                "logo": SimpleUploadedFile("bad.txt", b"hello", content_type="text/plain")
            },
        )
        self.assertFalse(form.is_valid())
        self.assertIn("logo", form.errors)

    def test_verification_expire_minutes_out_of_range(self):
        """验证码有效期超出 5-30 区间应被拒绝"""
        form_class = self.admin.get_form(DummyRequest())
        form = form_class(
            data={
                "name": "test",
                "provider": MailAccount.Provider.CUSTOM,
                "username": "a@example.com",
                "password": "pwd",
                "host": "smtp.example.com",
                "port": 587,
                "connection_security": "tls",
                "priority": 1,
                "is_default": False,
                "is_active": True,
                "verification_expire_minutes": 1,
            },
            files={},
        )
        self.assertFalse(form.is_valid())
        # 可在字段或非字段错误中提示
        self.assertTrue(
            "verification_expire_minutes" in form.errors
            or any("5-30" in err for err in form.non_field_errors())
            or "__all__" in form.errors
        )
