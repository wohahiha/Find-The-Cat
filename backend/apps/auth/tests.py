# -*- coding: utf-8 -*-
"""
认证与权限模块测试
- 确认应用加载
- RBAC 默认组与 manage_* 包含规则
"""
from __future__ import annotations

from django.apps import apps
from django.test import TestCase
from django.contrib.auth import get_user_model

from apps.auth.group import list_builtin_groups, sync_builtin_groups, assign_default_group
from apps.auth.rbac import DEFAULT_ADMIN_GROUP, DEFAULT_USER_GROUP, expand_with_implied

User = get_user_model()


class AuthAppSmokeTest(TestCase):
    """确认 AuthConfig 已注册"""

    def test_app_installed(self):
        self.assertTrue(apps.is_installed("apps.auth"))


class RBACDefaultsTests(TestCase):
    """验证默认 RBAC 组与 manage_* 包含关系"""

    def test_builtin_groups_synced(self):
        sync_builtin_groups()
        groups = list_builtin_groups()
        self.assertIn(DEFAULT_ADMIN_GROUP, groups)
        self.assertIn(DEFAULT_USER_GROUP, groups)
        self.assertTrue(any(code.startswith("contests.view_") for code in groups[DEFAULT_USER_GROUP]))
        # 管理组应包含管理与查看权限
        self.assertTrue(any(code.startswith("contests.manage_") for code in groups[DEFAULT_ADMIN_GROUP]))
        self.assertGreater(len(groups[DEFAULT_ADMIN_GROUP]), len(groups[DEFAULT_USER_GROUP]))

    def test_manage_permission_expands(self):
        perms = expand_with_implied(["problem_bank.manage_bank"])
        # manage_bank 应包含查看与导出导入等权限
        self.assertIn("problem_bank.view_bank", perms)
        self.assertIn("problem_bank.import_bank", perms)
        self.assertIn("problem_bank.export_bank", perms)

    def test_assign_default_group_for_staff_and_user(self):
        admin = User.objects.create_superuser(username="admin", email="a@example.com", password="pass1234")
        user = User.objects.create_user(username="player", email="p@example.com", password="pass1234")
        # 移除任何默认组，再调用 assign_default_group
        admin.groups.clear()
        user.groups.clear()
        assign_default_group(admin, is_admin=True)
        assign_default_group(user, is_admin=False)
        self.assertTrue(admin.groups.filter(name=DEFAULT_ADMIN_GROUP).exists())
        self.assertTrue(user.groups.filter(name=DEFAULT_USER_GROUP).exists())
