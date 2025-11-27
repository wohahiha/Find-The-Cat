from __future__ import annotations

from django.urls import path

from .views import (
    ProblemBankListView,
    BankChallengeListView,
    BankChallengeDetailView,
    BankChallengeSubmitView,
    BankImportFromContestView,
    BankImportChallengesView,
    BankExternalImportView,
    BankExportView,
)

# 路由调整：仅保留“题库”板块，所有导入/导出操作均在选定题库路径下进行
urlpatterns = [
    # 题库列表/创建
    path("", ProblemBankListView.as_view(), name="problem-bank-list"),
    # 题库内导入/导出操作（管理员）
    path("<str:bank_slug>/import/contest/", BankImportFromContestView.as_view(), name="problem-bank-import-contest"),
    path(
        "<str:bank_slug>/import/challenges/",
        BankImportChallengesView.as_view(),
        name="problem-bank-import-challenges",
    ),
    path("<str:bank_slug>/import/external/", BankExternalImportView.as_view(), name="problem-bank-import-external"),
    path("<str:bank_slug>/export/", BankExportView.as_view(), name="problem-bank-export"),
    # 题库题目列表/详情/提交
    path("<str:bank_slug>/", BankChallengeListView.as_view(), name="problem-bank-challenge-list"),
    path("<str:bank_slug>/<str:challenge_slug>/", BankChallengeDetailView.as_view(),
         name="problem-bank-challenge-detail"),
    path(
        "<str:bank_slug>/<str:challenge_slug>/submit/",
        BankChallengeSubmitView.as_view(),
        name="problem-bank-submit",
    ),
]
