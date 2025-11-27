from __future__ import annotations

from django.urls import path

from .views import (
    RegisterView,
    LoginView,
    CaptchaView,
    SendEmailVerificationView,
    PasswordResetRequestView,
    PasswordResetView,
    ProfileView,
    ChangePasswordView,
    ChangeEmailView,
    DeleteAccountView,
)

app_name = "accounts"

urlpatterns = [
    # 注册：公开接口，校验用户名/邮箱唯一与验证码
    path("auth/register/", RegisterView.as_view(), name="register"),
    # 登录：返回 JWT，支持用户名或邮箱
    path("auth/login/", LoginView.as_view(), name="login"),
    # 获取图形验证码：登录前调用
    path("auth/captcha/", CaptchaView.as_view(), name="captcha"),
    # 申请重置密码：发送邮箱验证码（节流/场景校验）
    path("auth/password/reset/request/", PasswordResetRequestView.as_view(), name="password-reset-request"),
    # 重置密码：消费验证码后设置新密码
    path("auth/password/reset/", PasswordResetView.as_view(), name="password-reset"),
    # 修改密码：登录态校验旧密码后设置新密码
    path("auth/password/change/", ChangePasswordView.as_view(), name="password-change"),
    # 发送邮箱验证码：注册/找回/绑定邮箱场景
    path("email/verification/", SendEmailVerificationView.as_view(), name="email-code"),
    # 变更邮箱：需要当前密码 + 新邮箱验证码
    path("email/change/", ChangeEmailView.as_view(), name="email-change"),
    # 个人资料：查看/更新当前用户信息
    path("me/", ProfileView.as_view(), name="profile"),
    # 注销账号：软删除当前用户，释放用户名/邮箱
    path("me/deactivate/", DeleteAccountView.as_view(), name="deactivate"),
]
# 账户相关路由配置：统一前缀按功能分组（auth/email/me），便于前端与权限管理
