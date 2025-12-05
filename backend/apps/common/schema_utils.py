# apps/common/schema_utils.py
from __future__ import annotations

from rest_framework import serializers
from drf_spectacular.utils import inline_serializer


_CACHE: dict[str, type[serializers.Serializer]] = {}


def _cached(name: str, builder):
    """简单缓存，避免重复生成同名 inline serializer 导致冲突"""
    if name not in _CACHE:
        _CACHE[name] = builder()
    return _CACHE[name]


def api_response_schema(name: str, data_fields: dict) -> serializers.Serializer:
    """
    构造统一响应 Schema：code/message/data/extra
    - name 用于生成唯一的响应/数据命名
    - data_fields 为 data 内部的字段定义
    """
    normalized_fields = {}
    for key, value in data_fields.items():
        if isinstance(value, type) and issubclass(value, serializers.Serializer):
            normalized_fields[key] = value()
        else:
            normalized_fields[key] = value
    data_serializer = inline_serializer(name=f"{name}Data", fields=normalized_fields)
    return inline_serializer(
        name=f"{name}Response",
        fields={
            "code": serializers.IntegerField(help_text="业务状态码，0 表示成功"),
            "message": serializers.CharField(help_text="提示信息"),
            "data": data_serializer,
            "extra": serializers.DictField(required=False, allow_null=True, help_text="附加信息"),
        },
    )


def list_response(name: str, item_serializer: serializers.Serializer, extra_fields: dict | None = None):
    """列表响应：data.items 为数组，可选附加字段"""
    items_field = item_serializer(many=True) if isinstance(item_serializer, type) and issubclass(item_serializer, serializers.Serializer) else item_serializer
    fields = {"items": items_field}
    if extra_fields:
        fields.update(extra_fields)
    return api_response_schema(name, fields)


# 常用数据结构
def contest_summary_serializer():
    return _cached(
        "ContestSummary",
        lambda: inline_serializer(
            name="ContestSummary",
            fields={
                "slug": serializers.CharField(help_text="比赛标识"),
                "name": serializers.CharField(help_text="比赛名称"),
                "description": serializers.CharField(help_text="描述", required=False, allow_blank=True),
                "start_time": serializers.DateTimeField(help_text="开始时间"),
                "end_time": serializers.DateTimeField(help_text="结束时间"),
                "status": serializers.CharField(help_text="状态"),
                "is_team_based": serializers.BooleanField(help_text="是否组队赛"),
            },
        ),
    )


def challenge_summary_serializer():
    return _cached(
        "ChallengeSummary",
        lambda: inline_serializer(
            name="ChallengeSummary",
            fields={
                "slug": serializers.CharField(help_text="题目标识"),
                "title": serializers.CharField(help_text="题目标题"),
                "category": serializers.CharField(required=False, allow_null=True, allow_blank=True, help_text="分类"),
                "current_points": serializers.IntegerField(help_text="当前可得分", required=False),
                "difficulty": serializers.CharField(required=False),
                "solved": serializers.BooleanField(required=False, help_text="是否已解（如有）"),
                "has_machine": serializers.BooleanField(required=False, help_text="是否启用靶机"),
            },
        ),
    )


def hint_serializer():
    return _cached(
        "HintItem",
        lambda: inline_serializer(
            name="HintItem",
            fields={
                "id": serializers.IntegerField(help_text="提示 ID", required=False),
                "title": serializers.CharField(help_text="提示标题"),
                "content": serializers.CharField(help_text="提示内容（未解锁可为空）", required=False, allow_blank=True),
                "order": serializers.IntegerField(help_text="排序", required=False),
            },
        ),
    )


def team_serializer():
    return _cached(
        "TeamSummary",
        lambda: inline_serializer(
            name="TeamSummary",
            fields={
                "id": serializers.IntegerField(help_text="队伍 ID"),
                "contest": serializers.CharField(help_text="比赛标识"),
                "name": serializers.CharField(help_text="队伍名称"),
                "slug": serializers.CharField(help_text="队伍标识"),
                "captain_id": serializers.IntegerField(help_text="队长用户 ID"),
                "member_count": serializers.IntegerField(help_text="队伍人数"),
                "is_active": serializers.BooleanField(help_text="是否有效"),
            },
        ),
    )


def submission_payload_serializer():
    return _cached(
        "SubmissionPayload",
        lambda: inline_serializer(
            name="SubmissionPayload",
            fields={
                "id": serializers.IntegerField(required=False),
                "status": serializers.CharField(help_text="提交状态", required=False),
                "is_correct": serializers.BooleanField(required=False),
                "awarded_points": serializers.IntegerField(required=False),
                "bonus_points": serializers.IntegerField(required=False),
                "blood_rank": serializers.IntegerField(required=False, allow_null=True),
                "message": serializers.CharField(required=False, allow_blank=True),
                "created_at": serializers.DateTimeField(required=False),
            },
        ),
    )


def problem_bank_serializer():
    return _cached(
        "ProblemBankSummary",
        lambda: inline_serializer(
            name="ProblemBankSummary",
            fields={
                "name": serializers.CharField(),
                "slug": serializers.CharField(),
                "description": serializers.CharField(required=False, allow_blank=True),
                "is_public": serializers.BooleanField(),
            },
        ),
    )


def bank_challenge_serializer():
    return _cached(
        "BankChallengeSummary",
        lambda: inline_serializer(
            name="BankChallengeSummary",
            fields={
                "slug": serializers.CharField(),
                "title": serializers.CharField(),
                "short_description": serializers.CharField(required=False, allow_blank=True),
                "difficulty": serializers.CharField(required=False),
                "solved": serializers.BooleanField(required=False),
            },
        ),
    )


def user_summary_serializer():
    return _cached(
        "UserSummary",
        lambda: inline_serializer(
            name="UserSummary",
            fields={
                "id": serializers.IntegerField(required=False),
                "username": serializers.CharField(),
                "email": serializers.EmailField(),
                "nickname": serializers.CharField(required=False, allow_blank=True),
                "avatar": serializers.CharField(required=False, allow_blank=True),
                "is_email_verified": serializers.BooleanField(required=False),
                "permissions": serializers.ListField(
                    child=serializers.CharField(),
                    required=False,
                    help_text="权限概览（中文标签）",
                ),
            },
        ),
    )


def announcement_serializer():
    return _cached(
        "Announcement",
        lambda: inline_serializer(
            name="Announcement",
            fields={
                "id": serializers.IntegerField(),
                "contest": serializers.CharField(),
                "title": serializers.CharField(),
                "content": serializers.CharField(),
                "is_active": serializers.BooleanField(),
                "created_at": serializers.DateTimeField(required=False),
                "updated_at": serializers.DateTimeField(required=False),
            },
        ),
    )


def category_serializer():
    return _cached(
        "ContestCategory",
        lambda: inline_serializer(
            name="ContestCategory",
            fields={
                "id": serializers.IntegerField(),
                "contest": serializers.CharField(required=False, allow_blank=True),
                "name": serializers.CharField(),
                "slug": serializers.CharField(),
                "description": serializers.CharField(required=False, allow_blank=True),
            },
        ),
    )


def machine_serializer():
    return _cached(
        "MachineInstance",
        lambda: inline_serializer(
            name="MachineInstance",
            fields={
                "id": serializers.IntegerField(),
                "contest": serializers.CharField(),
                "challenge": serializers.CharField(),
                "user": serializers.IntegerField(),
                "team": serializers.IntegerField(allow_null=True, required=False),
                "container_id": serializers.CharField(),
                "host": serializers.CharField(),
                "port": serializers.IntegerField(),
                "status": serializers.CharField(),
                "created_at": serializers.DateTimeField(),
                "updated_at": serializers.DateTimeField(),
            },
        ),
    )
