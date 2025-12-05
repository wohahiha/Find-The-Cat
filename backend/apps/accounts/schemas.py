"""账户相关的序列化与入参校验 Schema

定义登录、注册、修改资料、修改邮箱/密码、注销等请求的输入结构与校验规则
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional, ClassVar

from django.conf import settings
from django.core.validators import validate_email as django_validate_email
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.uploadedfile import UploadedFile

from apps.common.base.base_schema import BaseSchema
from apps.common.exceptions import ValidationError
from apps.common.utils.validators import (
    validate_password_strength,
    validate_url_optional,
    forbid_html,
    validate_image_file,
)

# EmailVerificationCode 已迁移至 system 模块
from apps.system.models import EmailVerificationCode

USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]{3,32}$")
EMAIL_CODE_PATTERN = re.compile(r"^\d{6}$")


def _validate_email(value: str) -> None:
    """
    邮箱格式校验：
    - 业务场景：注册/重置/修改邮箱等输入的统一邮箱格式检查
    - 模块角色：复用 Django 内置校验，统一转为业务异常
    - 参数 value：待校验邮箱字符串
    """
    try:
        django_validate_email(value)
    except DjangoValidationError as exc:
        raise ValidationError(message="邮箱格式不正确") from exc


def _validate_password(value: str) -> None:
    """
    密码复杂度校验：
    - 业务规则：统一复用 common.validators.validate_password_strength，长度 8-64 且必须包含字母和数字
    - 模块角色：被注册/修改密码/重置密码等校验复用，确保与后台创建用户一致
    """
    validate_password_strength(value, min_length=8, max_length=64)


@dataclass
class SendEmailCodeSchema(BaseSchema[None]):
    """
    发送邮箱验证码入参 Schema：
    - 用于注册/重置密码/绑定邮箱等场景的验证码发送请求
    - 自动执行 validate，确保邮箱格式正确且场景受支持
    """
    auto_validate: ClassVar[bool] = True

    # 邮箱地址：验证码接收目标
    email: str
    # 业务场景：限定 EmailVerificationCode.Scene
    scene: str

    def validate(self) -> None:
        """校验邮箱格式与场景合法性，避免发送到非法地址或不支持的业务场景"""
        _validate_email(self.email)
        if self.scene not in EmailVerificationCode.Scene.values:
            raise ValidationError(message="不支持的验证码场景")


@dataclass
class RegisterSchema(BaseSchema[None]):
    """
    注册入参 Schema：
    - 校验用户名格式、邮箱格式、密码强度与二次确认
    - 验证邮箱验证码格式
    """
    auto_validate: ClassVar[bool] = True

    # 用户名：3-32 位字母/数字/._-
    username: str
    # 邮箱：唯一登录与通知标识
    email: str
    # 密码：需符合复杂度
    password: str
    # 确认密码：需与密码一致
    confirm_password: str
    # 邮箱验证码：6 位数字
    email_code: str
    # 昵称：可选，默认回填为用户名
    nickname: Optional[str] = field(default=None)

    def validate(self) -> None:
        """逐项校验用户名、邮箱、密码与验证码格式，并比对两次密码，确保注册安全"""
        if not USERNAME_PATTERN.match(self.username):
            raise ValidationError(message="用户名需为 3-32 位字母/数字/._- 组合")

        _validate_email(self.email)
        _validate_password(self.password)

        if self.password != self.confirm_password:
            raise ValidationError(message="两次输入的密码不一致")

        if not EMAIL_CODE_PATTERN.match(self.email_code):
            raise ValidationError(message="验证码格式错误")


@dataclass
class LoginSchema(BaseSchema[None]):
    """
    登录入参 Schema：
    - 接收用户名或邮箱作为 identifier
    - 校验密码与图形验证码
    """
    auto_validate: ClassVar[bool] = True

    # identifier：用户名或邮箱，用于兼容双字段登录
    identifier: str  # 用户名或邮箱
    # 登录密码
    password: str
    # 图形验证码 key（后端生成）
    captcha_key: str = ""
    # 图形验证码用户输入
    captcha_code: str = ""
    # 记住登录（前端可选参数，后端可忽略，仅为兼容）
    remember: bool = False

    def validate(self) -> None:
        """校验登录凭据与图形验证码字段非空，identifier 长度需至少 3"""
        if not self.identifier or len(self.identifier) < 3:
            raise ValidationError(message="请输入正确的用户名或邮箱")
        if not self.password:
            raise ValidationError(message="请输入密码")
        allow_without_captcha = getattr(settings, "ALLOW_LOGIN_WITHOUT_CAPTCHA", False)
        if not allow_without_captcha:
            if not self.captcha_key or not self.captcha_code:
                raise ValidationError(message="请完成图形验证码")


@dataclass
class ResetPasswordSchema(BaseSchema[None]):
    """
    重置密码入参 Schema：
    - 通过邮箱 + 验证码 + 新密码完成重置
    - 校验新密码复杂度与两次输入一致性
    """
    auto_validate: ClassVar[bool] = True

    # 目标邮箱
    email: str
    # 邮箱验证码
    code: str
    # 新密码
    new_password: str
    # 确认新密码
    confirm_password: str

    def validate(self) -> None:
        """校验邮箱、验证码格式，并确保新密码符合复杂度且两次一致，避免弱密码与误操作"""
        _validate_email(self.email)
        if not EMAIL_CODE_PATTERN.match(self.code):
            raise ValidationError(message="验证码格式错误")
        _validate_password(self.new_password)
        if self.new_password != self.confirm_password:
            raise ValidationError(message="两次输入的密码不一致")


@dataclass
class ProfileUpdateSchema(BaseSchema[None]):
    """
    个人资料更新入参 Schema：
    - 支持昵称、头像、简介、组织、国家、个人主页的部分更新
    - 至少需提供一项更新字段
    """
    auto_validate: ClassVar[bool] = True

    # 昵称
    nickname: Optional[str] = None
    # 头像链接
    avatar: Optional[str] = None
    # 个人简介
    bio: Optional[str] = None
    # 所属组织
    organization: Optional[str] = None
    # 国家/地区
    country: Optional[str] = None
    # 个人主页
    website: Optional[str] = None

    def validate(self) -> None:
        """至少需要填写一个字段，否则提示无更新内容，避免空请求占用资源"""
        if not any(
            [
                self.nickname,
                self.avatar,
                self.bio,
                self.organization,
                self.country,
                self.website,
            ]
        ):
            raise ValidationError(message="请至少填写一项需要更新的资料")
        # 长度与格式校验，防止过长/恶意内容
        if self.nickname and len(self.nickname) > 32:
            raise ValidationError(message="昵称长度不可超过 32 个字符")
        if self.bio and len(self.bio) > 200:
            raise ValidationError(message="个人简介长度不可超过 200 个字符")
        if self.organization and len(self.organization) > 64:
            raise ValidationError(message="组织名称长度不可超过 64 个字符")
        if self.country and len(self.country) > 64:
            raise ValidationError(message="国家/地区长度不可超过 64 个字符")
        # 禁止 HTML
        for field_name, value in [
            ("昵称", self.nickname),
            ("个人简介", self.bio),
            ("组织", self.organization),
            ("国家/地区", self.country),
        ]:
            forbid_html(value, field_name=field_name)
        # 网址/头像需是合法 URL（可留空）
        if self.avatar:
            validate_url_optional(self.avatar, allow_blank=True)
        if self.website:
            validate_url_optional(self.website, allow_blank=True)


@dataclass
class ChangePasswordSchema(BaseSchema[None]):
    """
    修改密码入参 Schema：
    - 需要提供旧密码、邮箱验证码、新密码与确认新密码
    - 校验新密码复杂度、与旧密码不同且两次一致
    """
    auto_validate: ClassVar[bool] = True

    # 旧密码：用于身份验证
    old_password: str
    # 邮箱验证码：验证邮箱归属
    email_code: str
    # 新密码
    new_password: str
    # 确认新密码
    confirm_password: str

    def validate(self) -> None:
        """校验旧密码非空、验证码格式、新密码复杂度，以及新旧不同与两次一致，防止弱密码与误改"""
        if not self.old_password:
            raise ValidationError(message="请填写当前密码")
        if not EMAIL_CODE_PATTERN.match(self.email_code):
            raise ValidationError(message="验证码格式错误")
        _validate_password(self.new_password)
        if self.new_password == self.old_password:
            raise ValidationError(message="新密码不能与旧密码相同")
        if self.new_password != self.confirm_password:
            raise ValidationError(message="两次输入的新密码不一致")


@dataclass
class ChangeEmailSchema(BaseSchema[None]):
    """
    修改邮箱入参 Schema：
    - 需要当前密码、新邮箱与新邮箱验证码
    - 校验邮箱格式与验证码格式
    """
    auto_validate: ClassVar[bool] = True

    # 新邮箱
    new_email: str
    # 邮箱验证码
    email_code: str
    # 当前密码：用于身份校验
    current_password: str

    def validate(self) -> None:
        """校验当前密码非空、新邮箱格式与验证码格式，确保身份确认与邮箱有效性"""
        if not self.current_password:
            raise ValidationError(message="请填写当前密码")
        _validate_email(self.new_email)
        if not EMAIL_CODE_PATTERN.match(self.email_code):
            raise ValidationError(message="验证码格式错误")


@dataclass
class DeleteAccountSchema(BaseSchema[None]):
    """
    注销账户入参 Schema：
    - 需要用户输入当前密码作为二次确认
    """
    auto_validate: ClassVar[bool] = True

    # 当前密码：确认身份
    password: str

    def validate(self) -> None:
        """校验密码非空，确保用户明确确认注销操作"""
        if not self.password:
            raise ValidationError(message="请填写密码以确认身份")


@dataclass
class AvatarUploadSchema(BaseSchema[None]):
    """
    头像上传入参 Schema：
    - 承载上传的图片文件
    - 校验文件类型与大小，防止恶意上传
    """
    auto_validate: ClassVar[bool] = True

    # 上传的头像文件
    file: UploadedFile

    def validate(self) -> None:
        """校验文件存在、类型与大小，限制为常见图片格式且默认不超过 2MB"""
        if not self.file:
            raise ValidationError(message="请上传头像文件")
        validate_image_file(self.file, allowed_types={"image/png", "image/jpeg", "image/webp"}, max_size_mb=2)
