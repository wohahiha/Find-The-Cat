from __future__ import annotations

"""
权限集中台：
- 业务目标：统一维护整个平台的权限清单，以“ 大类-子类-具体功能 ”命名，便于后台展示与沟通。
- 模块角色：所有默认权限配置（内置用户组等）都依赖此处数据，避免分散硬编码。
"""

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

PermissionKey = Tuple[str, str]


@dataclass(frozen=True)
class PermissionItem:
    app_label: str
    codename: str
    category: str
    module: str
    action: str

    @property
    def label(self) -> str:
        return f"{self.category}-{self.module}-{self.action}"


ACTION_LABELS: Dict[str, str] = {
    "add": "新增",
    "change": "修改",
    "delete": "删除",
    "view": "查看",
}

_PERMISSION_MODELS: Sequence[Tuple[str, str, str, str]] = (
    ("accounts", "emailverificationcode", "账户管理", "邮箱验证码"),
    ("accounts", "mailaccount", "账户管理", "发信账号"),
    ("accounts", "playeruser", "账户管理", "参赛用户"),
    ("accounts", "staffuser", "账户管理", "管理员账号"),
    ("accounts", "user", "账户管理", "系统用户"),
    ("admin", "logentry", "系统审计", "后台操作日志"),
    ("auth", "group", "系统配置", "权限组"),
    ("auth", "permission", "系统配置", "权限定义"),
    ("challenges", "challenge", "题目管理", "题目"),
    ("challenges", "challengeattachment", "题目管理", "题目附件"),
    ("challenges", "challengehint", "题目管理", "题目提示"),
    ("challenges", "challengehintunlock", "题目管理", "提示解锁"),
    ("challenges", "challengetask", "题目管理", "题目子任务"),
    ("challenges", "challengecategory", "题目管理", "题目分类"),
    ("challenges", "challengesolve", "题目管理", "解题记录"),
    ("contenttypes", "contenttype", "系统配置", "模型注册"),
    ("contests", "contest", "赛事管理", "比赛"),
    ("contests", "contestannouncement", "赛事管理", "比赛公告"),
    ("contests", "team", "赛事管理", "战队"),
    ("contests", "teammember", "赛事管理", "队员"),
    ("machines", "machineinstance", "靶机管理", "靶机实例"),
    ("sessions", "session", "系统配置", "会话记录"),
    ("submissions", "submission", "提交计分", "提交记录"),
)


def _build_items() -> List[PermissionItem]:
    items: List[PermissionItem] = []
    for app_label, model, category, module in _PERMISSION_MODELS:
        for action_code, action_label in ACTION_LABELS.items():
            codename = f"{action_code}_{model}"
            items.append(
                PermissionItem(
                    app_label=app_label,
                    codename=codename,
                    category=category,
                    module=module,
                    action=action_label,
                )
            )
    return items


PERMISSION_ITEMS: Tuple[PermissionItem, ...] = tuple(_build_items())
PERMISSION_LABELS: Dict[PermissionKey, str] = {
    (item.app_label, item.codename): item.label for item in PERMISSION_ITEMS
}


def get_permission_label(value: str | PermissionKey) -> str:
    """
    将 Django 内部的 permission code（app.codename 或 (app, codename)）转换成
    定义好的中文名称。若未在权限集中定义，则回退到原始 code，便于排查。
    """

    if isinstance(value, tuple):
        app_label, codename = value
    else:
        if "." not in value:
            return value
        app_label, codename = value.split(".", 1)

    return PERMISSION_LABELS.get((app_label, codename), f"{app_label}.{codename}")


DEFAULT_ADMIN_GROUP = "Admins::Default"
DEFAULT_USER_GROUP = "Users::Default"


def _all_permission_keys() -> Tuple[PermissionKey, ...]:
    return tuple(PERMISSION_LABELS.keys())


def _default_user_view_permissions() -> Tuple[PermissionKey, ...]:
    keys: List[PermissionKey] = []
    for item in PERMISSION_ITEMS:
        if item.action != "查看":
            continue
        if item.category in {"赛事管理", "题目管理"}:
            keys.append((item.app_label, item.codename))
    return tuple(keys)


GROUP_PERMISSION_PRESETS: Dict[str, Tuple[PermissionKey, ...]] = {
    DEFAULT_ADMIN_GROUP: _all_permission_keys(),
    DEFAULT_USER_GROUP: _default_user_view_permissions(),
}


def iter_permission_labels(keys: Iterable[str | PermissionKey]) -> List[str]:
    """
    批量转换权限 code，保持输出顺序稳定。
    """

    labels: List[str] = []
    for key in keys:
        labels.append(get_permission_label(key))
    return labels
