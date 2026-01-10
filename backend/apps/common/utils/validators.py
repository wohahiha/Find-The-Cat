"""
校验工具集合：提供常用字段格式校验
"""

from __future__ import annotations

import re
from typing import Iterable

from django.core.validators import validate_email as django_validate_email
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError as DjangoUrlValidationError

from apps.common.exceptions import ValidationError

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_email(email: str) -> None:
    """校验邮箱格式，不通过抛出 ValidationError，统一邮件输入规则"""
    try:
        django_validate_email(email)
    except DjangoValidationError as exc:
        raise ValidationError(message="邮箱格式不正确") from exc


def validate_password_strength(password: str, min_length: int = 8, max_length: int = 64) -> None:
    """
    密码复杂度校验：
    - 长度需在 [min_length, max_length] 区间
    - 必须同时包含字母与数字，防止弱密码
    """
    if not min_length <= len(password) <= max_length:
        raise ValidationError(message=f"密码长度需在 {min_length}-{max_length} 位之间")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise ValidationError(message="密码需同时包含字母和数字")


def validate_slug(slug: str) -> None:
    """校验 slug 仅包含字母、数字、连字符与下划线"""
    if not re.match(r"^[a-zA-Z0-9_-]+$", slug):
        raise ValidationError(message="短标识仅能包含字母、数字、连字符或下划线")


def forbid_html(value: str, *, field_name: str = "字段") -> None:
    """禁止包含简单 HTML 标签，防止 XSS 注入"""
    if value and ("<" in value or ">" in value):
        raise ValidationError(message=f"{field_name} 不允许包含 HTML 标签")


def forbid_dangerous_html(value: str, *, field_name: str = "字段") -> None:
    """
    拒绝常见危险 HTML 片段（如 <script>/<iframe>/javascript: 等），降低 XSS 风险
    允许普通文本和 Markdown，但若检测到可执行片段则阻断
    """
    if not value:
        return
    lower = value.lower()
    dangerous_markers = [
        "<script",
        "javascript:",
        "onerror=",
        "onload=",
        "<iframe",
        "<object",
        "<embed",
        "svg/onload",
    ]
    if any(marker in lower for marker in dangerous_markers):
        raise ValidationError(message=f"{field_name} 含有潜在危险的 HTML/脚本片段")


def validate_url_optional(url: str, *, allow_blank: bool = True) -> None:
    """可选 URL 校验，空值可放过"""
    if allow_blank and not url:
        return
    validator = URLValidator()
    try:
        validator(url)
    except DjangoUrlValidationError as exc:
        raise ValidationError(message="URL 格式不正确") from exc


def validate_image_file(uploaded_file, *, allowed_types: Iterable[str] = None, max_size_mb: int = 2) -> None:
    """
    上传图片校验：
    - 限定 MIME 类型
    - 限定大小（MB）
    """
    if uploaded_file is None:
        return
    allowed_types = set(allowed_types or {"image/png", "image/jpeg", "image/webp"})
    content_type = getattr(uploaded_file, "content_type", "") or ""
    if content_type not in allowed_types:
        raise ValidationError(message="仅支持上传 PNG/JPEG/WEBP 图片作为 Logo")
    size = getattr(uploaded_file, "size", 0) or 0
    if size > max_size_mb * 1024 * 1024:
        raise ValidationError(message=f"图片大小不可超过 {max_size_mb}MB")


def validate_upload_file(
    uploaded_file,
    *,
    allowed_content_types: Iterable[str] | None = None,
    allowed_suffixes: Iterable[str] | None = None,
    max_size_mb: int = 10,
    field_name: str = "文件",
) -> None:
    """
    通用上传校验：MIME/后缀/大小
    """
    if uploaded_file is None:
        raise ValidationError(message=f"请上传{field_name}")
    content_type = (getattr(uploaded_file, "content_type", "") or "").lower()
    name_lower = (getattr(uploaded_file, "name", "") or "").lower()
    size = getattr(uploaded_file, "size", 0) or 0

    if allowed_content_types:
        allowed_content_types = {ct.lower() for ct in allowed_content_types}
        if content_type not in allowed_content_types:
            raise ValidationError(message=f"{field_name}类型不受支持，请检查文件格式")

    if allowed_suffixes and name_lower:
        suffix = "." + name_lower.split(".")[-1] if "." in name_lower else ""
        allowed_suffixes = {s.lower() for s in allowed_suffixes}
        if suffix and suffix not in allowed_suffixes:
            raise ValidationError(message=f"{field_name}类型不受支持，请检查文件后缀")

    if size > max_size_mb * 1024 * 1024:
        raise ValidationError(message=f"{field_name}大小不可超过 {max_size_mb}MB")
