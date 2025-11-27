from __future__ import annotations

from django.contrib import admin

from .models import ProblemBank, BankCategory, BankChallenge


class BankCategoryInline(admin.TabularInline):
    """题库内分类配置：在题库详情页按需维护"""

    model = BankCategory
    extra = 0
    fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


class BankChallengeInline(admin.TabularInline):
    """题库内题目列表：基础字段维护，附件/提示另行在题目页处理"""

    model = BankChallenge
    extra = 0
    fields = ("title", "slug", "category", "flag_type", "is_active")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(ProblemBank)
class ProblemBankAdmin(admin.ModelAdmin):
    """题库后台：仅保留“题库”板块，分类与题目在题库详情内维护"""

    list_display = ("name", "is_public", "created_at")
    search_fields = ("name", "slug")
    list_filter = ("is_public",)
    prepopulated_fields = {"slug": ("name",)}
    inlines = [BankCategoryInline, BankChallengeInline]

# 其余模型不单独出现在后台菜单，避免多余板块：
# - BankCategory/BankChallenge 通过题库内联管理
# - BankSolve 仅用于用户已解标记，无需后台查询
