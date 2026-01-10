from __future__ import annotations

from typing import Optional
from django.utils.text import slugify

from apps.common.base.base_repo import BaseRepo
from apps.common.exceptions import NotFoundError

from .models import ProblemBank, BankCategory, BankChallenge, BankAttachment, BankHint, BankSolve


class ProblemBankRepo(BaseRepo[ProblemBank]):
    """题库仓储：创建/获取题库，按公开状态筛选"""

    model = ProblemBank

    def get_by_id(self, pk: int) -> ProblemBank:
        try:
            return self.filter(pk=pk).get()
        except ProblemBank.DoesNotExist as exc:  # type: ignore[attr-defined]
            raise NotFoundError(message="题库不存在") from exc

    def get_by_slug(self, slug: str) -> ProblemBank:
        try:
            return self.filter(slug=slug).get()
        except ProblemBank.DoesNotExist as exc:  # type: ignore[attr-defined]
            raise NotFoundError(message="题库不存在") from exc


class BankCategoryRepo(BaseRepo[BankCategory]):
    """题库分类仓储：按名称生成 slug 并获取/创建"""

    model = BankCategory

    def get_or_create_slug(self, bank: ProblemBank, name: str) -> BankCategory:
        slug = slugify(name) or name.lower()
        obj, _ = self.model.objects.get_or_create(bank=bank, slug=slug, defaults={"name": name})
        return obj


class BankChallengeRepo(BaseRepo[BankChallenge]):
    """题库题目仓储：按题库+slug 获取、列表"""

    model = BankChallenge

    def get_by_slug(self, *, bank: ProblemBank, slug: str) -> BankChallenge:
        try:
            return (
                self.filter(bank=bank, slug=slug)
                .select_related("bank", "category", "author")
                .prefetch_related("attachments", "hints")
                .get()
            )
        except BankChallenge.DoesNotExist as exc:  # type: ignore[attr-defined]
            raise NotFoundError(message="题库题目不存在") from exc

    def list_active(self, *, bank: ProblemBank):
        return (
            self.filter(bank=bank, is_active=True)
            .select_related("bank", "category", "author")
            .prefetch_related("attachments", "hints")
        )


class BankAttachmentRepo(BaseRepo[BankAttachment]):
    """题库附件仓储：用于同步附件列表"""

    model = BankAttachment


class BankHintRepo(BaseRepo[BankHint]):
    """题库提示仓储：按排序返回"""

    model = BankHint

    def list_for_challenge(self, challenge: BankChallenge):
        return self.filter(challenge=challenge).order_by("order", "id")


class BankSolveRepo(BaseRepo[BankSolve]):
    """题库解题记录仓储：标记与查询已解题"""

    model = BankSolve

    def has_solved(self, *, challenge: BankChallenge, user) -> bool:
        return self.filter(challenge=challenge, user=user).exists()

    def get_record(self, *, challenge: BankChallenge, user) -> Optional[BankSolve]:
        return self.filter(challenge=challenge, user=user).first()
