"""
题库服务聚合：
- ProblemBankCreateService：创建题库
- BankImportFromContestService / BankImportChallengesService：从比赛或指定题目导入（深拷贝）
- BankExternalImportService：占位支持外部 zip 导入
- BankExportService：导出题库到 zip（含附件/提示元数据）
- BankChallengeSubmitService：题库作答，不计分，仅记录已解状态
"""

from __future__ import annotations

import io
import zipfile
from django.db import transaction
from django.utils import timezone
from django.conf import settings

from apps.common.base.base_service import BaseService
from apps.common.exceptions import ValidationError, ConflictError, NotFoundError, PermissionDeniedError
from apps.accounts.models import User
from apps.challenges.repo import ChallengeRepo
from apps.contests.repo import ContestRepo
from apps.notifications.services import fanout_notifications, build_dedup_key
from apps.notifications.models import Notification

from .models import ProblemBank, BankChallenge, BankSolve
from .repo import (
    ProblemBankRepo,
    BankCategoryRepo,
    BankChallengeRepo,
    BankAttachmentRepo,
    BankHintRepo,
    BankSolveRepo,
)
from .importer import BankChallengeImporter
from .schemas import (
    ProblemBankCreateSchema,
    BankImportFromContestSchema,
    BankImportChallengesSchema,
    BankExternalImportSchema,
    BankExportSchema,
    BankChallengeSubmitSchema,
    BankChallengeUpdateSchema,
    ProblemBankUpdateSchema,
)
from .serializers import serialize_bank
from apps.common.infra.logger import get_logger, logger_extra

logger = get_logger(__name__)


def _notify_public_bank_challenge(bank: ProblemBank, challenge: BankChallenge, *, type: str) -> None:
    """向所有活跃用户推送公共题库题目的变更"""
    if not bank.is_public:
        return
    users = list(User.objects.filter(is_active=True, is_staff=False))
    if not users:
        return
    bucket = getattr(challenge, "updated_at", timezone.now()).isoformat(timespec="minutes")
    dedup = build_dedup_key(
        type=type,
        challenge=None,
        bucket=bucket,
        extra=f"bank-{getattr(bank, 'id', None)}-{getattr(challenge, 'id', None)}",
    )
    fanout_notifications(
        users,
        type=type,
        title=f"题库更新：{challenge.title}",
        body=bank.name,
        payload={
            "bank": bank.slug,
            "challenge": challenge.slug,
        },
        dedup_key=dedup,
    )


class BankContextService:
    """
    题库上下文服务：统一题库/题目获取与权限校验，避免视图层手写重复逻辑
    """

    def __init__(
            self,
            bank_repo: ProblemBankRepo | None = None,
            challenge_repo: BankChallengeRepo | None = None,
    ):
        self.bank_repo = bank_repo or ProblemBankRepo()
        self.challenge_repo = challenge_repo or BankChallengeRepo()

    def _resolve_bank(self, bank_slug_or_id: str) -> ProblemBank:
        """
        支持 slug 或数字 ID 的题库定位，未找到抛出业务级 NotFoundError
        """
        try:
            return self.bank_repo.get_by_slug(bank_slug_or_id)
        except NotFoundError:
            try:
                bank_id = int(bank_slug_or_id)
            except (TypeError, ValueError) as exc:
                raise NotFoundError(message="题库不存在") from exc
            return self.bank_repo.get_by_id(bank_id)

    def _ensure_visible(self, bank: ProblemBank, user: User) -> None:
        """
        校验题库是否对当前用户可见：公开或管理员，否则抛权限异常
        """
        if bank.is_public or getattr(user, "is_staff", False):
            return
        raise PermissionDeniedError(message="题库未公开")

    def get_bank_for_user(self, user: User, bank_slug_or_id: str) -> ProblemBank:
        """获取当前用户可见的题库对象"""
        bank = self._resolve_bank(bank_slug_or_id)
        self._ensure_visible(bank, user)
        return bank

    def get_challenge_for_user(self, user: User, bank_slug_or_id: str, challenge_slug: str) -> tuple[ProblemBank, BankChallenge]:
        """获取当前用户可访问的题库题目"""
        bank = self.get_bank_for_user(user, bank_slug_or_id)
        challenge = self.challenge_repo.get_by_slug(bank=bank, slug=challenge_slug)
        return bank, challenge


class ProblemBankCreateService(BaseService[ProblemBank]):
    """创建题库服务：仅管理员使用"""

    def __init__(self, bank_repo: ProblemBankRepo | None = None):
        self.bank_repo = bank_repo or ProblemBankRepo()

    def perform(self, schema: ProblemBankCreateSchema) -> ProblemBank:
        payload = schema.to_dict(exclude_none=True)
        bank = self.bank_repo.create(payload)
        logger.info("创建题库", extra=logger_extra({"bank": bank.name}))
        return bank


class ProblemBankUpdateService(BaseService[ProblemBank]):
    """更新题库服务：仅管理员使用"""

    def __init__(self, bank_repo: ProblemBankRepo | None = None):
        self.bank_repo = bank_repo or ProblemBankRepo()

    def perform(self, schema: ProblemBankUpdateSchema) -> ProblemBank:
        bank = self.bank_repo.get_by_slug(schema.bank_slug)
        payload = schema.to_dict(exclude_none=True)
        payload.pop("bank_slug", None)
        if payload.get("name"):
            bank.name = payload["name"]
        if "description" in payload:
            bank.description = payload.get("description", "") or ""
        if "is_public" in payload:
            bank.is_public = bool(payload["is_public"])
        bank.save(update_fields=["name", "description", "is_public", "updated_at"])
        logger.info(
            "更新题库",
            extra=logger_extra({"bank": bank.slug, "is_public": bank.is_public}),
        )
        return bank


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
        self.importer = BankChallengeImporter(
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
        imported = self.importer.copy_many(bank=bank, challenges=challenges)
        logger.info(
            "比赛题目导入题库",
            extra=logger_extra({"bank": bank.name, "contest": contest.slug, "count": len(imported)}),
        )
        for ch in imported:
            _notify_public_bank_challenge(bank, ch, type=Notification.Type.CHALLENGE_NEW)
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
        self.importer = BankChallengeImporter(
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
            imported = self.importer.copy_many(bank=bank, challenges=qs)
        else:
            raise ValidationError(message="暂不支持题库间导入，请指定比赛标识")
        logger.info(
            "部分题目导入题库",
            extra=logger_extra({"bank": bank.name, "contest": getattr(contest, "slug", None), "count": len(imported)}),
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
            # 确保时间可序列化
            if isinstance(bank_payload.get("created_at"), str):
                pass
            elif bank_payload.get("created_at"):
                bank_payload["created_at"] = bank_payload["created_at"].isoformat()
            if isinstance(bank_payload.get("updated_at"), str):
                pass
            elif bank_payload.get("updated_at"):
                bank_payload["updated_at"] = bank_payload["updated_at"].isoformat()
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
            context_service: BankContextService | None = None,
    ):
        self.bank_repo = bank_repo or ProblemBankRepo()
        self.bank_challenge_repo = bank_challenge_repo or BankChallengeRepo()
        self.solve_repo = solve_repo or BankSolveRepo()
        self.context_service = context_service or BankContextService(
            bank_repo=self.bank_repo,
            challenge_repo=self.bank_challenge_repo,
        )

    def perform(self, user: User, bank_slug: str, challenge_slug: str, schema: BankChallengeSubmitSchema) -> BankSolve:
        bank, challenge = self.context_service.get_challenge_for_user(user, bank_slug, challenge_slug)
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


class BankChallengeUpdateService(BaseService[BankChallenge]):
    """更新题库题目：支持编辑题面/Flag/难度/分类/上下线"""

    def __init__(
            self,
            bank_repo: ProblemBankRepo | None = None,
            challenge_repo: BankChallengeRepo | None = None,
            category_repo: BankCategoryRepo | None = None,
    ):
        self.bank_repo = bank_repo or ProblemBankRepo()
        self.challenge_repo = challenge_repo or BankChallengeRepo()
        self.category_repo = category_repo or BankCategoryRepo()

    @transaction.atomic
    def perform(self, schema: BankChallengeUpdateSchema) -> BankChallenge:
        bank = self.bank_repo.get_by_slug(schema.bank_slug)
        challenge = self.challenge_repo.get_by_slug(bank=bank, slug=schema.challenge_slug)
        update_payload = schema.to_dict(exclude_none=True)
        update_payload.pop("bank_slug", None)
        update_payload.pop("challenge_slug", None)
        category_name = update_payload.pop("category", None)
        if category_name:
            category = self.category_repo.get_or_create_slug(bank=bank, name=category_name)
            update_payload["category"] = category
        if update_payload:
            challenge = self.challenge_repo.update(challenge, update_payload)
        logger.info(
            "更新题库题目",
            extra=logger_extra({"bank": bank.slug, "challenge": challenge.slug}),
        )
        _notify_public_bank_challenge(bank, challenge, type=Notification.Type.CHALLENGE_UPDATED)
        return challenge
