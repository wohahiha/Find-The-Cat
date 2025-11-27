from __future__ import annotations

"""
题库服务聚合：
- ProblemBankCreateService：创建题库
- BankImportFromContestService / BankImportChallengesService：从比赛或指定题目导入（深拷贝）
- BankExternalImportService：占位支持外部 zip 导入
- BankExportService：导出题库到 zip（含附件/提示元数据）
- BankChallengeSubmitService：题库作答，不计分，仅记录已解状态
"""

import io
import zipfile
from django.db import transaction
from django.utils import timezone
from django.conf import settings

from apps.common.base.base_service import BaseService
from apps.common.exceptions import ValidationError, ConflictError, NotFoundError
from apps.accounts.models import User
from apps.challenges.repo import ChallengeRepo
from apps.challenges.models import Challenge
from apps.contests.repo import ContestRepo

from .models import ProblemBank, BankChallenge, BankAttachment, BankHint, BankSolve
from .repo import (
    ProblemBankRepo,
    BankCategoryRepo,
    BankChallengeRepo,
    BankAttachmentRepo,
    BankHintRepo,
    BankSolveRepo,
)
from .schemas import (
    ProblemBankCreateSchema,
    BankImportFromContestSchema,
    BankImportChallengesSchema,
    BankExternalImportSchema,
    BankExportSchema,
    BankChallengeSubmitSchema,
)
from .serializers import serialize_bank, serialize_challenge
from apps.common.infra.logger import get_logger, logger_extra

logger = get_logger(__name__)


class ProblemBankCreateService(BaseService[ProblemBank]):
    """创建题库服务：仅管理员使用"""

    def __init__(self, bank_repo: ProblemBankRepo | None = None):
        self.bank_repo = bank_repo or ProblemBankRepo()

    def perform(self, schema: ProblemBankCreateSchema) -> ProblemBank:
        payload = schema.to_dict(exclude_none=True)
        bank = self.bank_repo.create(payload)
        logger.info("创建题库", extra=logger_extra({"bank": bank.name}))
        return bank


class _BankChallengeCopier:
    """内部工具：将比赛题目深拷贝到题库"""

    def __init__(
            self,
            bank_repo: ProblemBankRepo,
            bank_challenge_repo: BankChallengeRepo,
            category_repo: BankCategoryRepo,
            attachment_repo: BankAttachmentRepo,
            hint_repo: BankHintRepo,
    ):
        self.bank_repo = bank_repo
        self.bank_challenge_repo = bank_challenge_repo
        self.category_repo = category_repo
        self.attachment_repo = attachment_repo
        self.hint_repo = hint_repo

    def copy_challenge(self, *, bank: ProblemBank, challenge: Challenge, author=None) -> BankChallenge:
        category = None
        if challenge.category:
            category = self.category_repo.get_or_create_slug(bank, challenge.category.name)
        # 生成唯一 slug，避免冲突
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
            "is_active": True,
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


class BankImportFromContestService(BaseService[list[BankChallenge]]):
    """从比赛导入全部题目到题库（深拷贝）"""

    def __init__(
            self,
            bank_repo: ProblemBankRepo | None = None,
            contest_repo: ContestRepo | None = None,
            challenge_repo: ChallengeRepo | None = None,
            bank_challenge_repo: BankChallengeRepo | None = None,
            category_repo: BankCategoryRepo | None = None,
            attachment_repo: BankAttachmentRepo | None = None,
            hint_repo: BankHintRepo | None = None,
    ):
        self.bank_repo = bank_repo or ProblemBankRepo()
        self.contest_repo = contest_repo or ContestRepo()
        self.challenge_repo = challenge_repo or ChallengeRepo()
        self.copier = _BankChallengeCopier(
            bank_repo=self.bank_repo,
            bank_challenge_repo=bank_challenge_repo or BankChallengeRepo(),
            category_repo=category_repo or BankCategoryRepo(),
            attachment_repo=attachment_repo or BankAttachmentRepo(),
            hint_repo=hint_repo or BankHintRepo(),
        )

    @transaction.atomic
    def perform(self, schema: BankImportFromContestSchema) -> list[BankChallenge]:
        bank = self._get_bank(schema.bank_slug)
        contest = self.contest_repo.get_by_slug(schema.contest_slug)
        # 正在进行的比赛禁止导入，避免泄题
        if not contest.has_ended:
            raise ConflictError(message="比赛尚未结束，禁止导入题库")
        challenges = self.challenge_repo.filter(contest=contest).prefetch_related("attachments", "hints", "category")
        imported: list[BankChallenge] = []
        for ch in challenges:
            imported.append(self.copier.copy_challenge(bank=bank, challenge=ch))
        logger.info(
            "比赛题目导入题库",
            extra=logger_extra({"bank": bank.name, "contest": contest.slug, "count": len(imported)}),
        )
        return imported

    def _get_bank(self, bank_slug: str) -> ProblemBank:
        """根据 slug 获取题库，兼容数字 ID 以便旧前端过渡"""
        try:
            return self.bank_repo.get_by_slug(bank_slug)
        except Exception:
            try:
                return self.bank_repo.get_by_id(int(bank_slug))
            except Exception:
                raise NotFoundError(message="题库不存在")


class BankImportChallengesService(BaseService[list[BankChallenge]]):
    """从指定比赛导入部分题目"""

    def __init__(
            self,
            bank_repo: ProblemBankRepo | None = None,
            contest_repo: ContestRepo | None = None,
            challenge_repo: ChallengeRepo | None = None,
            bank_challenge_repo: BankChallengeRepo | None = None,
            category_repo: BankCategoryRepo | None = None,
            attachment_repo: BankAttachmentRepo | None = None,
            hint_repo: BankHintRepo | None = None,
    ):
        self.bank_repo = bank_repo or ProblemBankRepo()
        self.contest_repo = contest_repo or ContestRepo()
        self.challenge_repo = challenge_repo or ChallengeRepo()
        self.copier = _BankChallengeCopier(
            bank_repo=self.bank_repo,
            bank_challenge_repo=bank_challenge_repo or BankChallengeRepo(),
            category_repo=category_repo or BankCategoryRepo(),
            attachment_repo=attachment_repo or BankAttachmentRepo(),
            hint_repo=hint_repo or BankHintRepo(),
        )

    @transaction.atomic
    def perform(self, schema: BankImportChallengesSchema) -> list[BankChallenge]:
        bank = self._get_bank(schema.bank_slug)
        contest = self.contest_repo.get_by_slug(schema.contest_slug) if schema.contest_slug else None
        if contest and not contest.has_ended:
            raise ConflictError(message="比赛尚未结束，禁止导入题库")
        imported: list[BankChallenge] = []
        if contest:
            qs = self.challenge_repo.filter(contest=contest, slug__in=schema.challenge_slugs).prefetch_related(
                "attachments", "hints", "category"
            )
            for ch in qs:
                imported.append(self.copier.copy_challenge(bank=bank, challenge=ch))
        else:
            raise ValidationError(message="暂不支持题库间导入，请指定比赛标识")
        logger.info(
            "部分题目导入题库",
            extra=logger_extra({"bank": bank.name, "contest": getattr(contest, 'slug', None), "count": len(imported)}),
        )
        return imported

    def _get_bank(self, bank_slug: str) -> ProblemBank:
        """根据 slug 获取题库，兼容数字 ID"""
        try:
            return self.bank_repo.get_by_slug(bank_slug)
        except Exception:
            try:
                return self.bank_repo.get_by_id(int(bank_slug))
            except Exception:
                raise NotFoundError(message="题库不存在")


class BankExternalImportService(BaseService[list[BankChallenge]]):
    """外部 zip 导入占位：解析 zip 并创建题库题目"""

    def perform(self, schema: BankExternalImportSchema, *, content: bytes) -> list[BankChallenge]:
        # TODO: 实现具体解析规则，当前先抛出提示，避免静默失败
        raise ValidationError(message="外部导入尚未实现，请稍后使用比赛导入或后台录入")


class BankExportService(BaseService[dict]):
    """导出题库：打包元数据与附件链接为 zip"""

    atomic_enabled = False

    def __init__(
            self,
            bank_repo: ProblemBankRepo | None = None,
            bank_challenge_repo: BankChallengeRepo | None = None,
    ):
        self.bank_repo = bank_repo or ProblemBankRepo()
        self.bank_challenge_repo = bank_challenge_repo or BankChallengeRepo()

    def perform(self, schema: BankExportSchema) -> dict:
        bank = self._get_bank(schema.bank_slug)
        challenges = (
            self.bank_challenge_repo.filter(bank=bank)
            .select_related("category")
            .prefetch_related("attachments", "hints")
        )
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # 元数据写入 JSON 格式
            import json

            bank_payload = serialize_bank(bank)
            bank_payload["created_at"] = bank_payload["created_at"].isoformat() if bank_payload.get(
                "created_at") else None
            bank_payload["updated_at"] = bank_payload["updated_at"].isoformat() if bank_payload.get(
                "updated_at") else None
            meta = {"bank": bank_payload, "challenges": []}
            for ch in challenges:
                created_at = ch.created_at.isoformat() if ch.created_at else None
                updated_at = ch.updated_at.isoformat() if ch.updated_at else None
                meta["challenges"].append(
                    {
                        "title": ch.title,
                        "slug": ch.slug,
                        "short_description": ch.short_description,
                        "content": ch.content,
                        "difficulty": ch.difficulty,
                        "flag_type": ch.flag_type,
                        "flag": ch.flag,
                        "dynamic_prefix": ch.dynamic_prefix,
                        "flag_case_insensitive": ch.flag_case_insensitive,
                        "category": ch.category.name if ch.category else None,
                        "created_at": created_at,
                        "updated_at": updated_at,
                        "attachments": [{"name": a.name, "url": a.url} for a in ch.attachments.all()],
                        "hints": [{"title": h.title, "content": h.content} for h in ch.hints.all()],
                    }
                )
            zf.writestr("metadata.json", json.dumps(meta, ensure_ascii=False, indent=2))
        buf.seek(0)
        return {"filename": f"problem_bank_{bank.id}.zip", "content": buf.getvalue()}

    def _get_bank(self, bank_slug: str) -> ProblemBank:
        """根据 slug 获取题库，兼容数字 ID 形式"""
        try:
            return self.bank_repo.get_by_slug(bank_slug)
        except Exception:
            try:
                return self.bank_repo.get_by_id(int(bank_slug))
            except Exception:
                raise NotFoundError(message="题库不存在")


class BankChallengeSubmitService(BaseService[BankSolve]):
    """题库作答服务：校验 Flag 并记录解题，不计分"""

    def __init__(
            self,
            bank_repo: ProblemBankRepo | None = None,
            bank_challenge_repo: BankChallengeRepo | None = None,
            solve_repo: BankSolveRepo | None = None,
    ):
        self.bank_repo = bank_repo or ProblemBankRepo()
        self.bank_challenge_repo = bank_challenge_repo or BankChallengeRepo()
        self.solve_repo = solve_repo or BankSolveRepo()

    def perform(self, user: User, bank_slug: str, challenge_slug: str, schema: BankChallengeSubmitSchema) -> BankSolve:
        try:
            bank = self.bank_repo.get_by_slug(bank_slug)
        except Exception:
            try:
                bank = self.bank_repo.get_by_id(int(bank_slug))
            except Exception:
                raise NotFoundError(message="题库不存在")
        if not bank.is_public and not user.is_staff:
            raise NotFoundError(message="题库未公开")
        challenge = self.bank_challenge_repo.get_by_slug(bank=bank, slug=challenge_slug)
        if not challenge.is_active:
            raise ConflictError(message="题目未开放")
        if self.solve_repo.has_solved(challenge=challenge, user=user):
            raise ConflictError(message="你已解出该题")
        secret = getattr(settings, "SECRET_KEY", "ftc-bank-flag")
        if not challenge.check_flag(schema.flag, user=user, secret=secret):
            raise ValidationError(message="提交内容不正确")
        solve = self.solve_repo.create({"challenge": challenge, "user": user, "solved_at": timezone.now()})
        logger.info(
            "题库作答成功",
            extra=logger_extra({"bank": bank.name, "challenge": challenge.slug, "user_id": user.id}),
        )
        return solve
