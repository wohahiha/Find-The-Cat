from __future__ import annotations

from django.urls import path

from .views import (
    ProblemBankListView,
    BankChallengeListView,
    BankChallengeDetailView,
    BankChallengeSubmitView,
    ProblemBankMetaView,
)

# 路由调整：仅保留“题库”板块，所有导入/导出操作均在选定题库路径下进行
urlpatterns = [
    # 题库列表/创建
    path("", ProblemBankListView.as_view(), name="problem-bank-list"),
    # 题库元信息查看/更新
    path("<str:bank_slug>/meta/", ProblemBankMetaView.as_view(), name="problem-bank-meta"),
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
