from __future__ import annotations

from typing import Optional

from django.db import transaction
from django.utils.text import slugify

from apps.common.base.base_repo import BaseRepo
from apps.common.exceptions import NotFoundError, ConflictError

from .models import Contest, Team, TeamMember, ContestAnnouncement
from apps.accounts.models import User

# 仓储层：封装比赛、公告、队伍的 ORM 访问，提供业务友好的查询与写入。


class ContestRepo(BaseRepo[Contest]):
    """比赛仓储：提供 slug 查询等快捷方法。"""
    model = Contest

    def get_by_slug(self, slug: str) -> Contest:
        """通过 slug 获取比赛，未找到抛业务级 404。"""
        # 提供统一的比赛获取入口，视图与服务层复用
        try:
            return self.filter(slug=slug).get()
        except Contest.DoesNotExist as exc:  # type: ignore[attr-defined]
            raise NotFoundError(message="比赛不存在") from exc


class ContestAnnouncementRepo(BaseRepo[ContestAnnouncement]):
    """比赛公告仓储：提供按比赛筛选与获取。"""

    model = ContestAnnouncement

    def list_active(self, contest: Contest):
        """获取比赛下所有有效公告，按创建时间倒序。"""
        # 仅返回 is_active=True 的公告，供前台列表展示
        return self.filter(contest=contest, is_active=True).order_by("-created_at")

    def get_by_id(self, pk: int) -> ContestAnnouncement:
        """根据 ID 获取公告，未找到抛业务级 404。"""
        # 更新或删除公告前先确保记录存在
        try:
            return self.filter(pk=pk).get()
        except ContestAnnouncement.DoesNotExist as exc:  # type: ignore[attr-defined]
            raise NotFoundError(message="公告不存在") from exc


class TeamRepo(BaseRepo[Team]):
    """队伍仓储：生成唯一 slug、创建队伍、维护邀请码。"""
    model = Team

    def generate_slug(self, name: str, contest: Contest) -> str:
        """根据队伍名称与比赛生成唯一 slug；避免同名队伍冲突。"""
        # 生成队伍 slug，若重名则递增后缀避免冲突
        base = slugify(name) or "team"
        slug = base
        idx = 1
        while self.filter(contest=contest, slug=slug).exists():
            idx += 1
            slug = f"{base}-{idx}"
        return slug

    def create_team(self, *, contest: Contest, captain: User, name: str, description: str = "") -> Team:
        """封装创建队伍逻辑，便于服务层复用，默认创建队长为创建者。"""
        # 封装创建队伍：自动生成 slug 并落库
        slug = self.generate_slug(name, contest)
        return self.create(
            {
                "contest": contest,
                "name": name,
                "slug": slug,
                "description": description,
                "captain": captain,
            }
        )

    def get_by_id(self, pk: int) -> Team:
        """依据主键获取队伍，常用于权限校验或后续更新。"""
        # 通过主键获取队伍，未找到抛业务级 404
        try:
            return self.filter(pk=pk).get()
        except Team.DoesNotExist as exc:  # type: ignore[attr-defined]
            raise NotFoundError(message="队伍不存在") from exc

    def reset_invite_token(self, team: Team, *, token: str) -> Team:
        """重置队伍邀请码。"""
        # 重置时同时刷新更新时间，避免邀请码长期未更新
        team.invite_token = token
        team.save(update_fields=["invite_token", "updated_at"])
        return team


class TeamMemberRepo(BaseRepo[TeamMember]):
    """队伍成员仓储：维护成员增删与查询。"""
    model = TeamMember

    def create_member(self, *, team: Team, user: User, role: str) -> TeamMember:
        """创建成员关系：确保未重复加入后写入队伍成员表。"""
        # 创建成员前校验是否已在队伍内
        if self.filter(team=team, user=user, is_active=True).exists():
            raise ConflictError(message="用户已在当前队伍中")
        return self.create(
            {
                "team": team,
                "user": user,
                "role": role,
            }
        )

    def get_membership(self, *, contest: Contest, user: User) -> Optional[TeamMember]:
        """查询某用户在指定比赛中的有效队伍成员关系，便于权限判断。"""
        # 查询用户在某比赛的有效队伍关系
        return (
            self.filter(team__contest=contest, user=user, is_active=True)
            .select_related("team")
            .first()
        )

    @transaction.atomic
    def remove_member(self, membership: TeamMember) -> None:
        """移除成员：在事务内标记失效，供退出/解散使用。"""
        membership.is_active = False
        membership.save(update_fields=["is_active"])

    def active_members(self, team: Team):
        """获取队伍当前有效成员列表，常用于解散或统计。"""
        # 获取队伍当前有效成员列表
        return self.filter(team=team, is_active=True).select_related("user")
