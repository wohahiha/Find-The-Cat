from __future__ import annotations

from django.contrib import admin

from .models import Contest, Team, TeamMember

# 后台注册：仅负责 Django Admin 展示配置，不包含业务逻辑。


@admin.register(Contest)
class ContestAdmin(admin.ModelAdmin):
    """比赛模型后台展示：支持基础字段检索与过滤。"""
    # 列表展示关键字段，便于运营查看时间与赛制
    list_display = ("name", "slug", "visibility", "start_time", "end_time", "is_team_based")
    # 允许通过名称、slug 搜索
    search_fields = ("name", "slug")
    # 按可见性与赛制过滤
    list_filter = ("visibility", "is_team_based")
    # 根据 name 自动生成 slug
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    """队伍后台展示：展示队伍状态与邀请码。"""
    # 列表展示队伍与队长、邀请码等信息
    list_display = ("name", "contest", "captain", "is_active", "invite_token")
    # 支持按比赛与有效状态过滤
    list_filter = ("contest", "is_active")
    # 支持按名称/slug/邀请码搜索
    search_fields = ("name", "slug", "invite_token")
    # 根据名称预生成 slug
    prepopulated_fields = {"slug": ("name",)}


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    """队伍成员后台展示：便于运营查看成员角色与状态。"""
    # 列表展示队伍、用户、角色与加入时间
    list_display = ("team", "user", "role", "is_active", "joined_at")
    # 按角色、有效性过滤
    list_filter = ("role", "is_active")
    # 按队伍名、用户名、邮箱搜索
    search_fields = ("team__name", "user__username", "user__email")
