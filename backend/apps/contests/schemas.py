# apps/contests/schemas.py

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar, Optional

from django.utils import timezone

from apps.common.base.base_schema import BaseSchema
from apps.common.exceptions import ValidationError
from apps.common.utils.validators import forbid_dangerous_html


# Schema 层：负责请求入参的结构化与校验，禁止写业务逻辑


@dataclass
class ContestCreateSchema(BaseSchema[None]):
    """
    创建比赛入参：
    - 覆盖比赛基础信息、时间配置与赛制开关
    - 自动校验时间合法性与人数上限
    """
    auto_validate: ClassVar[bool] = True
    # 比赛名称
    name: str
    # 比赛标识 slug
    slug: str
    # 比赛描述
    description: str = ""
    # 可见性
    visibility: str = "public"
    # 开赛时间
    start_time: datetime = None  # type: ignore[assignment]
    # 结束时间
    end_time: datetime = None  # type: ignore[assignment]
    # 封榜时间
    freeze_time: Optional[datetime] = None
    # 报名开始/截止时间
    registration_start_time: Optional[datetime] = None
    registration_end_time: Optional[datetime] = None
    # 团队赛（True） / 个人赛（False）
    is_team_based: bool = True
    # 队伍人数上限
    max_team_members: int = 4
    # 题目分类列表
    categories: list[str] = field(default_factory=list)

    def validate(self) -> None:
        """校验时间顺序、封榜区间与人数上限"""

        def ensure_dt(value: datetime | str | None) -> datetime:
            # 将字符串或 naive datetime 统一转换为时区感知的 datetime
            if isinstance(value, str):
                dt = datetime.fromisoformat(value)
            else:
                dt = value  # type: ignore[assignment]
            if dt is None:
                raise ValidationError(message="须指定比赛的开始和结束时间")
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, timezone.get_default_timezone())
            return dt

        if not self.name:
            raise ValidationError(message="比赛名称不能为空")
        forbid_dangerous_html(self.name, field_name="比赛名称")
        if not self.slug:
            raise ValidationError(message="比赛标识不能为空")
        if self.description:
            forbid_dangerous_html(self.description, field_name="比赛描述")
        self.start_time = ensure_dt(self.start_time)
        self.end_time = ensure_dt(self.end_time)
        if self.end_time <= self.start_time:
            raise ValidationError(message="结束时间必须晚于开始时间")
        if self.registration_start_time:
            self.registration_start_time = ensure_dt(self.registration_start_time)
        if self.registration_end_time:
            self.registration_end_time = ensure_dt(self.registration_end_time)
        if self.registration_start_time and self.registration_end_time and self.registration_start_time > self.registration_end_time:
            raise ValidationError(message="报名开始时间需早于报名截止时间")
        if self.registration_start_time and self.registration_start_time > self.start_time:
            raise ValidationError(message="报名开始时间不能晚于比赛开始时间")
        if self.registration_end_time and self.registration_end_time > self.start_time:
            raise ValidationError(message="报名截止时间不能晚于比赛开始时间")
        if self.freeze_time:
            self.freeze_time = ensure_dt(self.freeze_time)
            if not (self.start_time <= self.freeze_time <= self.end_time):
                raise ValidationError(message="封榜时间必须介于比赛时间范围内")
        if self.max_team_members < 1:
            raise ValidationError(message="队伍人数下限为 1")
        cleaned_categories: list[str] = []
        for name in self.categories:
            name_str = str(name).strip()
            if not name_str:
                continue
            if name_str in cleaned_categories:
                continue
            cleaned_categories.append(name_str)
        self.categories = cleaned_categories


@dataclass
class ContestUpdateSchema(BaseSchema[None]):
    """
    更新比赛入参：支持部分字段更新，校验时间顺序与人数上限
    """
    auto_validate: ClassVar[bool] = True
    # 比赛标识
    contest_slug: str
    # 比赛名称
    name: Optional[str] = None
    # 比赛描述
    description: Optional[str] = None
    # 可见性
    visibility: Optional[str] = None
    # 开赛时间
    start_time: Optional[datetime] = None
    # 结束时间
    end_time: Optional[datetime] = None
    # 封榜时间
    freeze_time: Optional[datetime] = None
    # 报名开始/截止时间
    registration_start_time: Optional[datetime] = None
    registration_end_time: Optional[datetime] = None
    # 团队赛（True） / 个人赛（False）
    is_team_based: Optional[bool] = None
    # 队伍人数上限
    max_team_members: Optional[int] = None

    def validate(self) -> None:
        """基础校验：确保存在比赛标识，队伍人数合法"""
        if not self.contest_slug:
            raise ValidationError(message="缺少比赛标识")
        if self.name:
            forbid_dangerous_html(self.name, field_name="比赛名称")
        if self.description:
            forbid_dangerous_html(self.description, field_name="比赛描述")
        if self.max_team_members is not None and self.max_team_members < 1:
            raise ValidationError(message="队伍人数下限为 1")


@dataclass
class AnnouncementCreateSchema(BaseSchema[None]):
    """
    创建或维护比赛公告的入参
    """
    auto_validate: ClassVar[bool] = True
    # 比赛标识
    contest_slug: str
    # 公告标题
    title: str
    # 公告摘要
    summary: str
    # 公告正文
    content: str
    # 是否生效
    is_active: bool = True

    def validate(self) -> None:
        """校验公告基础字段"""
        if not self.contest_slug:
            raise ValidationError(message="缺少比赛标识")
        if not self.title:
            raise ValidationError(message="公告标题不能为空")
        forbid_dangerous_html(self.title, field_name="公告标题")
        if not self.summary:
            raise ValidationError(message="公告摘要不能为空")
        forbid_dangerous_html(self.summary, field_name="公告摘要")
        if not self.content:
            raise ValidationError(message="公告内容不能为空")
        forbid_dangerous_html(self.content, field_name="公告内容")


@dataclass
class TeamCreateSchema(BaseSchema[None]):
    """创建队伍入参：包含比赛标识与队伍信息"""
    auto_validate: ClassVar[bool] = True
    # 比赛标识
    contest_slug: str
    # 队伍名称
    name: str
    # 队伍简介
    description: str = ""

    def validate(self) -> None:
        """校验队伍名称必填"""
        if not self.name:
            raise ValidationError(message="队伍名称不能为空")
        forbid_dangerous_html(self.name, field_name="队伍名称")
        if self.description:
            forbid_dangerous_html(self.description, field_name="队伍简介")


@dataclass
class TeamJoinSchema(BaseSchema[None]):
    """加入队伍入参：通过比赛标识与邀请码"""
    auto_validate: ClassVar[bool] = True
    # 比赛标识
    contest_slug: str
    # 队伍邀请码
    invite_token: str

    def validate(self) -> None:
        """校验邀请码必填"""
        if not self.invite_token:
            raise ValidationError(message="请输入队伍邀请码")


@dataclass
class TeamLeaveSchema(BaseSchema[None]):
    """退出队伍入参：仅需比赛标识"""
    auto_validate: ClassVar[bool] = True
    # 比赛标识
    contest_slug: str

    def validate(self) -> None:
        """校验比赛标识必填"""
        if not self.contest_slug:
            raise ValidationError(message="缺少比赛标识")


@dataclass
class TeamDisbandSchema(BaseSchema[None]):
    """解散队伍入参：仅管理员或队长使用"""
    auto_validate: ClassVar[bool] = True
    # 队伍主键
    team_id: int

    def validate(self) -> None:
        """校验队伍 ID 合法性"""
        if self.team_id <= 0:
            raise ValidationError(message="非法的队伍 ID")


@dataclass
class TeamInviteResetSchema(BaseSchema[None]):
    """
    重置队伍邀请码入参
    """
    auto_validate: ClassVar[bool] = True
    # 队伍主键
    team_id: int

    def validate(self) -> None:
        """校验队伍 ID 合法性"""
        if self.team_id <= 0:
            raise ValidationError(message="非法的队伍 ID")


@dataclass
class TeamTransferSchema(BaseSchema[None]):
    """
    队长移交入参
    """
    auto_validate: ClassVar[bool] = True
    # 队伍主键
    team_id: int
    # 新队长用户 ID
    new_captain_id: int

    def validate(self) -> None:
        """校验队伍与新队长 ID 合法性"""
        if self.team_id <= 0:
            raise ValidationError(message="非法的队伍 ID")
        if self.new_captain_id <= 0:
            raise ValidationError(message="非法的队员 ID")


@dataclass
class ContestCategoryUpdateSchema(BaseSchema[None]):
    """
    比赛题目分类更新入参：列表传入分类名称集合
    """

    auto_validate: ClassVar[bool] = True
    contest_slug: str
    categories: list[str] = field(default_factory=list)

    def validate(self) -> None:
        if not self.contest_slug:
            raise ValidationError(message="缺少比赛标识")
        cleaned: list[str] = []
        for name in self.categories:
            value = str(name).strip()
            if not value:
                continue
            if value in cleaned:
                continue
            cleaned.append(value)
        self.categories = cleaned
