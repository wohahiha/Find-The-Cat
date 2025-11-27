"""
自定义 Django 认证后端

用途：
- 后台登录时绕过 is_active 的硬过滤，让表单有机会返回自定义“账户失效”提示（避免默认 invalid_login 覆盖）
- 仅放开 user_can_authenticate，不直接放行停用账号，最终仍由表单/权限控制
"""

from __future__ import annotations

from django.contrib.auth.backends import ModelBackend


class AdminAuthBackend(ModelBackend):
    """
    后台登录专用的认证后端，允许返回 is_active=False 的用户对象，好给出明确的失效提示，登录是否通过仍由表单决定

    - 业务场景：后台管理员登录需要提示账户已失效，而不是模糊的“用户名或密码错误”
    - 模块角色：调整 Django 的 user_can_authenticate 行为，让上层表单处理失效提示
    - 功能：仅放行校验，不改变最终登录授权，安全决策仍由 AdminAuthenticationForm 完成
    """

    def user_can_authenticate(self, user) -> bool:  # type: ignore[override]
        # 不在此处拦截 is_active，将最终决策交给 AdminAuthenticationForm/confirm_login_allowed
        # 参数 user：Django 认证获取到的用户实例，即便 is_active=False 也返回 True 以便上层返回中文提示
        return True
