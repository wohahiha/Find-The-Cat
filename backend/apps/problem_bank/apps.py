from __future__ import annotations

from django.apps import AppConfig


class ProblemBankConfig(AppConfig):
    """题库模块应用配置"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.problem_bank"
    label = "problem_bank"
    verbose_name = "Problem Bank"
