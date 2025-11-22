from __future__ import annotations

from django.contrib import admin

from .models import ChallengeCategory, Challenge, ChallengeSolve

# 后台注册：配置题目、分类与解题记录的 Django Admin 展示。


@admin.register(ChallengeCategory)
class ChallengeCategoryAdmin(admin.ModelAdmin):
    """题目分类后台：支持名称/slug 搜索与自动填充。"""
    # 列表展示字段
    list_display = ("name", "slug")
    # 支持按名称/slug 搜索
    search_fields = ("name", "slug")
    # 根据 name 自动生成 slug
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    """题目后台：查看题目基础信息与状态。"""
    # 列表展示标题、所属比赛与分值等
    list_display = ("title", "contest", "category", "difficulty", "base_points", "is_active")
    # 过滤器：按比赛、分类、难度、上线状态
    list_filter = ("contest", "category", "difficulty", "is_active")
    # 搜索：标题、slug、简介
    search_fields = ("title", "slug", "short_description")
    # 自动生成 slug
    prepopulated_fields = {"slug": ("title",)}


@admin.register(ChallengeSolve)
class ChallengeSolveAdmin(admin.ModelAdmin):
    """解题记录后台：查看得分与解题时间。"""
    # 列表展示解题核心信息
    list_display = ("challenge", "user", "team", "awarded_points", "solved_at")
    # 过滤：按所属比赛
    list_filter = ("challenge__contest",)
