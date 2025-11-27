from __future__ import annotations

from .models import ProblemBank, BankChallenge, BankHint


def serialize_bank(bank: ProblemBank) -> dict:
    """题库序列化：返回基础信息"""
    return {
        "id": bank.id,
        "name": bank.name,
        "description": bank.description,
        "is_public": bank.is_public,
        "created_at": bank.created_at,
        "updated_at": bank.updated_at,
    }


def serialize_hint(hint: BankHint) -> dict:
    """题库提示：统一免费，直接返回内容"""
    return {
        "id": hint.id,
        "title": hint.title,
        "content": hint.content,
        "order": hint.order,
    }


def serialize_challenge(challenge: BankChallenge, *, solved: bool = False) -> dict:
    """题库题目序列化：用于列表与详情"""
    return {
        "id": challenge.id,
        "bank": challenge.bank_id,
        "title": challenge.title,
        "slug": challenge.slug,
        "short_description": challenge.short_description,
        "content": challenge.content,
        "category": challenge.category.name if challenge.category else None,
        "difficulty": challenge.difficulty,
        "is_active": challenge.is_active,
        "attachments": [
            {"id": att.id, "name": att.name, "url": att.url, "order": att.order}
            for att in challenge.attachments.all().order_by("order", "id")
        ],
        "hints": [
            serialize_hint(hint)
            for hint in challenge.hints.all().order_by("order", "id")
        ],
        "solved": solved,
    }
