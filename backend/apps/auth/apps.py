# -*- coding: utf-8 -*-
from django.apps import AppConfig


class AuthConfig(AppConfig):
    """
    认证与权限（轻量级 RBAC）应用配置
    - label 设置为 ftc_auth 以避免与 django.contrib.auth 冲突
    - 后续将承载 OAuth2、角色/权限管理等
    """

    name = "apps.auth"
    label = "ftc_auth"
    verbose_name = "Authentication And Authorization"
