"""
校验工具集合：提供常用字段格式校验。
"""

from __future__ import annotations

import re
from typing import Optional

from django.core.validators import validate_email as django_validate_email
from django.core.exceptions import ValidationError as DjangoValidationError

from apps.common.exceptions import ValidationError

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_email(email: str) -> None:
    """校验邮箱格式，不通过抛出 ValidationError，统一邮件输入规则。"""
    try:
        django_validate_email(email)
    except DjangoValidationError as exc:
        raise ValidationError(message="邮箱格式不正确") from exc


def validate_password_strength(password: str, min_length: int = 8) -> None:
    """
    简单密码强度校验：
    - 长度不少于 min_length；
    - 同时包含字母与数字。
    """
    if len(password) < min_length:
        raise ValidationError(message=f"密码长度需至少 {min_length} 位")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise ValidationError(message="密码需同时包含字母和数字")


def validate_slug(slug: str) -> None:
    """校验 slug 仅包含字母、数字、连字符与下划线。"""
    if not re.match(r"^[a-zA-Z0-9_-]+$", slug):
        raise ValidationError(message="短标识仅能包含字母、数字、连字符或下划线")
