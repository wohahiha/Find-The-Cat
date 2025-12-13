from __future__ import annotations

from django.http import HttpRequest

from .models import ProblemBank, BankChallenge, BankHint


def _full_url(url: str | None, request: HttpRequest | None) -> str | None:
    if not url:
        return url
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if request:
        try:
            return request.build_absolute_uri(url)
        except Exception:
            return url
    return url


def serialize_bank(bank: ProblemBank) -> dict:
    """题库序列化：返回基础信息"""
    return {
        "id": bank.id,
        "name": bank.name,
        "description": bank.description,
        "is_public": bank.is_public,
        "slug": bank.slug,
        "created_at": bank.created_at,
        "updated_at": bank.updated_at,
    }


def serialize_hint(hint: BankHint) -> dict:
    """题库提示：返回内容与付费标记（题库默认不扣分，前端自行控制解锁展示）"""
    return {
        "id": hint.id,
        "title": hint.title,
        "content": hint.content,
        "order": hint.order,
        "is_free": getattr(hint, "is_free", True),
        "cost": getattr(hint, "cost", 0),
        "unlocked": False,
    }


def serialize_challenge(
    challenge: BankChallenge,
    *,
    solved: bool = False,
    request: HttpRequest | None = None,
) -> dict:
    """题库题目序列化：用于列表与详情"""
    has_machine = bool(getattr(challenge, "machine_contest_slug", "") and getattr(challenge, "machine_challenge_slug", ""))
    return {
        "id": challenge.id,
        "bank": challenge.bank_id,
        "title": challenge.title,
        "slug": challenge.slug,
        "short_description": challenge.short_description,
        "content": challenge.content,
        "category": challenge.category.name if challenge.category else None,
        "category_name": challenge.category.name if challenge.category else None,
        "category_slug": challenge.category.slug if challenge.category else None,
        "difficulty": challenge.difficulty,
        "is_active": challenge.is_active,
        "has_machine": has_machine,
        "machine_contest_slug": challenge.machine_contest_slug or None,
        "machine_challenge_slug": challenge.machine_challenge_slug or None,
        "attachments": [
            {
                "id": att.id,
                "name": att.name,
                "url": _full_url(att.url, request),
                "download_url": _full_url(att.url, request),
                "order": att.order,
            }
            for att in challenge.attachments.all().order_by("order", "id")
        ],
        "hints": [serialize_hint(hint) for hint in challenge.hints.all().order_by("order", "id")],
        "solved": solved,
    }
