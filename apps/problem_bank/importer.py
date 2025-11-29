from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from apps.problem_bank.models import ProblemBank, BankChallenge, BankCategory
from apps.problem_bank.repo import (
    ProblemBankRepo,
    BankChallengeRepo,
    BankCategoryRepo,
    BankAttachmentRepo,
    BankHintRepo,
)
from apps.challenges.models import Challenge


@dataclass
class BankChallengeImporter:
    """
    题库题目导入工具：支持从比赛题目深拷贝至题库
    - 复制题面/附件/提示
    - 自动处理 slug 冲突
    - 允许覆盖目标分类与可见性
    """

    bank_repo: ProblemBankRepo
    bank_challenge_repo: BankChallengeRepo
    category_repo: BankCategoryRepo
    attachment_repo: BankAttachmentRepo
    hint_repo: BankHintRepo

    @classmethod
    def default(cls) -> "BankChallengeImporter":
        """提供默认依赖，便于在服务层/后台直接实例化"""
        return cls(
            bank_repo=ProblemBankRepo(),
            bank_challenge_repo=BankChallengeRepo(),
            category_repo=BankCategoryRepo(),
            attachment_repo=BankAttachmentRepo(),
            hint_repo=BankHintRepo(),
        )

    def copy_many(
            self,
            *,
            bank: ProblemBank,
            challenges: Iterable[Challenge],
            author=None,
            target_category: BankCategory | None = None,
            is_active: bool = True,
    ) -> list[BankChallenge]:
        """批量复制题目"""
        created: list[BankChallenge] = []
        for challenge in challenges:
            created.append(
                self.copy_challenge(
                    bank=bank,
                    challenge=challenge,
                    author=author,
                    target_category=target_category,
                    is_active=is_active,
                )
            )
        return created

    def copy_challenge(
            self,
            *,
            bank: ProblemBank,
            challenge: Challenge,
            author=None,
            target_category: BankCategory | None = None,
            is_active: bool = True,
    ) -> BankChallenge:
        """
        复制单题：
        - 若传入 target_category 则使用指定题库分类，否则按比赛分类名称自动同步
        - is_active 控制导入后是否可见
        """
        category = target_category
        if category is None and challenge.category:
            category = self.category_repo.get_or_create_slug(bank, challenge.category.name)
        base_slug = challenge.slug
        slug = base_slug
        idx = 1
        while self.bank_challenge_repo.filter(bank=bank, slug=slug).exists():
            idx += 1
            slug = f"{base_slug}-{idx}"
        data = {
            "bank": bank,
            "category": category,
            "title": challenge.title,
            "slug": slug,
            "short_description": challenge.short_description,
            "content": challenge.content,
            "difficulty": challenge.difficulty,
            "flag": challenge.flag,
            "flag_case_insensitive": challenge.flag_case_insensitive,
            "flag_type": challenge.flag_type,
            "dynamic_prefix": challenge.dynamic_prefix,
            "is_active": is_active,
            "author": author or challenge.author,
        }
        bank_challenge = self.bank_challenge_repo.create(data)
        self._copy_attachments(bank_challenge, challenge)
        self._copy_hints(bank_challenge, challenge)
        return bank_challenge

    def _copy_attachments(self, bank_challenge: BankChallenge, challenge: Challenge) -> None:
        for att in challenge.attachments.all().order_by("order", "id"):
            self.attachment_repo.create(
                {
                    "challenge": bank_challenge,
                    "name": att.name,
                    "url": att.url,
                    "order": att.order,
                }
            )

    def _copy_hints(self, bank_challenge: BankChallenge, challenge: Challenge) -> None:
        for idx, hint in enumerate(challenge.hints.all().order_by("order", "id"), start=1):
            self.hint_repo.create(
                {
                    "challenge": bank_challenge,
                    "title": hint.title,
                    "content": hint.content,
                    "order": hint.order or idx,
                }
            )
