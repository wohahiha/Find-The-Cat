# apps/common/schema_utils.py
from __future__ import annotations

from rest_framework import serializers
from drf_spectacular.utils import inline_serializer, OpenApiParameter


_CACHE: dict[str, type[serializers.Serializer]] = {}


def _cached(name: str, builder):
    """简单缓存，避免重复生成同名 inline serializer 导致冲突"""
    if name not in _CACHE:
        _CACHE[name] = builder()
    return _CACHE[name]


def api_response_schema(
    name: str,
    data_fields: dict,
    *,
    extra_serializer: serializers.Field | None = None,
) -> serializers.Serializer:
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
            "extra": extra_serializer
            if extra_serializer
            else serializers.DictField(required=False, allow_null=True, help_text="附加信息"),
        },
    )


def pagination_meta_serializer():
    return _cached(
        "PaginationMeta",
        lambda: inline_serializer(
            name="PaginationMeta",
            fields={
                "page": serializers.IntegerField(help_text="当前页码（从 1 开始）"),
                "page_size": serializers.IntegerField(help_text="每页条数"),
                "total": serializers.IntegerField(help_text="总条数"),
                "total_pages": serializers.IntegerField(help_text="总页数", required=False, allow_null=True),
                "has_next": serializers.BooleanField(help_text="是否有下一页"),
                "has_previous": serializers.BooleanField(help_text="是否有上一页"),
                "next_page": serializers.IntegerField(help_text="下一页页码", required=False, allow_null=True),
                "previous_page": serializers.IntegerField(help_text="上一页页码", required=False, allow_null=True),
            },
        ),
    )


def pagination_parameters() -> list[OpenApiParameter]:
    """通用分页查询参数"""
    return [
        OpenApiParameter(
            name="page",
            location=OpenApiParameter.QUERY,
            description="页码（从 1 开始）",
            required=False,
            type=int,
        ),
        OpenApiParameter(
            name="page_size",
            location=OpenApiParameter.QUERY,
            description="每页条数",
            required=False,
            type=int,
        ),
    ]


def list_response(
    name: str,
    item_serializer: serializers.Serializer,
    extra_fields: dict | None = None,
    *,
    paginated: bool = False,
):
    """列表响应：data.items 为数组，可选附加字段，支持分页元信息"""
    items_field = (
        item_serializer(many=True)
        if isinstance(item_serializer, type) and issubclass(item_serializer, serializers.Serializer)
        else item_serializer
    )
    fields = {"items": items_field}
    if extra_fields:
        fields.update(extra_fields)
    return api_response_schema(
        name,
        fields,
        extra_serializer=pagination_meta_serializer() if paginated else None,
    )


# 常用数据结构
def contest_summary_serializer(**kwargs):
    cls = _cached(
        "ContestSummary",
        lambda: inline_serializer(
            name="ContestSummary",
            fields={
                "slug": serializers.CharField(help_text="比赛标识"),
                "name": serializers.CharField(help_text="比赛名称"),
                "description": serializers.CharField(help_text="描述", required=False, allow_blank=True),
                "start_time": serializers.DateTimeField(help_text="开始时间"),
                "end_time": serializers.DateTimeField(help_text="结束时间"),
                "freeze_time": serializers.DateTimeField(help_text="封榜时间", required=False, allow_null=True),
                "registration_start_time": serializers.DateTimeField(help_text="报名开始时间", required=False, allow_null=True),
                "registration_end_time": serializers.DateTimeField(help_text="报名截止时间", required=False, allow_null=True),
                "status": serializers.CharField(help_text="状态"),
                "is_team_based": serializers.BooleanField(help_text="是否组队赛"),
                "max_team_members": serializers.IntegerField(help_text="最大队员数", required=False, allow_null=True),
                "registration_status": serializers.BooleanField(help_text="当前用户是否已报名（需登录时返回）", required=False, allow_null=True),
                "registration_valid": serializers.BooleanField(help_text="报名是否有效（团队赛未组队则为 False）", required=False, allow_null=True),
                "my_team_id": serializers.IntegerField(help_text="当前用户在该比赛的队伍ID（组队赛且已加入时返回）", required=False, allow_null=True),
                "my_team_name": serializers.CharField(help_text="当前用户在该比赛的队伍名称", required=False, allow_null=True, allow_blank=True),
                "user_badge": serializers.CharField(help_text="用户侧副状态（registration_closed/registration_invalid/team_missing/frozen/finished/registered）", required=False, allow_blank=True, allow_null=True),
            },
        ),
    )
    return cls(**kwargs) if kwargs else cls


def challenge_summary_serializer(**kwargs):
    cls = _cached(
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
    # 兼容缓存中已是实例的情况
    if isinstance(cls, serializers.Serializer):
        return cls if not kwargs else cls.__class__(**kwargs)
    return cls(**kwargs) if kwargs else cls


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


def team_serializer(**kwargs):
    cls = _cached(
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
                "description": serializers.CharField(help_text="队伍简介", required=False, allow_blank=True),
                "invite_token": serializers.CharField(help_text="队伍邀请码", required=False, allow_blank=True),
            },
        ),
    )
    return cls(**kwargs) if kwargs else cls


def submission_payload_serializer(**kwargs):
    cls = _cached(
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
    if isinstance(cls, serializers.Serializer):
        return cls if not kwargs else cls.__class__(**kwargs)
    return cls(**kwargs) if kwargs else cls


def scoreboard_entry_serializer(**kwargs):
    """记分板条目：兼容团队赛与个人赛"""
    cls = _cached(
        "ScoreboardEntry",
        lambda: inline_serializer(
            name="ScoreboardEntry",
            fields={
                "type": serializers.ChoiceField(choices=["team", "user"], help_text="榜单类型：team/user"),
                "rank": serializers.IntegerField(help_text="排名"),
                "score": serializers.IntegerField(help_text="总分"),
                "bonus_score": serializers.IntegerField(help_text="额外分数", required=False),
                "is_me": serializers.BooleanField(help_text="是否为当前用户/队伍", required=False, allow_null=True),
                "name": serializers.CharField(help_text="队伍或选手名称", required=False, allow_blank=True),
                "team_id": serializers.IntegerField(help_text="队伍 ID", required=False, allow_null=True),
                "user_id": serializers.IntegerField(help_text="用户 ID", required=False, allow_null=True),
                "solves": serializers.ListSerializer(
                    child=inline_serializer(
                        name="ScoreboardSolveEntry",
                        fields={
                            "challenge": serializers.CharField(help_text="题目标识"),
                            "points": serializers.IntegerField(help_text="得分"),
                            "bonus_points": serializers.IntegerField(help_text="额外得分", required=False),
                            "base_points": serializers.IntegerField(help_text="基础得分", required=False),
                            "solved_at": serializers.CharField(help_text="解题时间", required=False),
                        },
                    ),
                    help_text="解题明细",
                ),
                "team": inline_serializer(
                    name="ScoreboardTeam",
                    fields={
                        "id": serializers.IntegerField(),
                        "name": serializers.CharField(),
                        "slug": serializers.CharField(),
                    },
                    required=False,
                    allow_null=True,
                ),
                "user": inline_serializer(
                    name="ScoreboardUser",
                    fields={
                        "id": serializers.IntegerField(),
                        "username": serializers.CharField(),
                    },
                    required=False,
                    allow_null=True,
                ),
            },
        ),
    )
    if isinstance(cls, serializers.Serializer):
        return cls if not kwargs else cls.__class__(**kwargs)
    return cls(**kwargs) if kwargs else cls


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
                "avatar": serializers.CharField(required=False, allow_blank=True, allow_null=True),
                "is_email_verified": serializers.BooleanField(required=False),
                "permissions": serializers.ListField(
                    child=serializers.CharField(),
                    required=False,
                    help_text="权限概览（中文标签）",
                ),
            },
        ),
    )


def announcement_serializer(**kwargs):
    cls = _cached(
        "Announcement",
        lambda: inline_serializer(
            name="Announcement",
            fields={
                "id": serializers.IntegerField(),
                "contest": serializers.CharField(),
                "title": serializers.CharField(),
                "summary": serializers.CharField(),
                "content": serializers.CharField(),
                "is_active": serializers.BooleanField(),
                "created_at": serializers.DateTimeField(required=False),
                "updated_at": serializers.DateTimeField(required=False),
            },
        ),
    )
    if isinstance(cls, serializers.Serializer):
        return cls if not kwargs else cls.__class__(**kwargs)
    return cls(**kwargs) if kwargs else cls


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
                "extend_count": serializers.IntegerField(required=False),
                "expires_at": serializers.DateTimeField(required=False, allow_null=True),
                "remaining_seconds": serializers.IntegerField(required=False, allow_null=True),
                "created_at": serializers.DateTimeField(),
                "updated_at": serializers.DateTimeField(),
            },
        ),
    )
