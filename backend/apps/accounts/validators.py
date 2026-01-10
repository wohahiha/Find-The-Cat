"""
后台与框架密码验证器：
- 统一复用业务侧的密码复杂度规则，避免 Admin 与 API 不一致
- 通过 Django AUTH_PASSWORD_VALIDATORS 接入
"""

from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError

from apps.common.exceptions import ValidationError as BizValidationError
from apps.common.utils.validators import validate_password_strength


class AccountPasswordValidator:
    """
    统一的密码校验器
    - 规则：长度 8-64，且同时包含字母与数字
    - 入口：Django 密码验证（Admin 创建/修改用户）
    """

    def validate(self, password: str, user=None) -> None:
        """校验密码强度，不通过时转为 Django ValidationError"""
        try:
            validate_password_strength(password, min_length=8, max_length=64)
        except BizValidationError as exc:
            # 转换为 Django 可识别的异常，便于表单提示
            raise DjangoValidationError(exc.message) from exc

    def get_help_text(self) -> str:
        """后台表单帮助文本，直观提示当前规则"""
        return "密码需为 8-64 位，且同时包含字母和数字。"
