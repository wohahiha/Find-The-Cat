"""
轻量级 RBAC 权限定义（apps.auth.rbac）

设计目标：
- 权限命名贴合实际业务模块（accounts/contests/challenges/submissions/machines/problem_bank/system/auth）
- 仅定义“有业务意义的动作”而非机械 CRUD
- manage_* 权限自动包含相关子操作，减小授权成本
- 默认管理员组：拥有全部权限；默认普通用户组：仅具备前台需要的查看/提交能力
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Set, Tuple


@dataclass(frozen=True)
class PermissionDef:
    """权限定义数据结构"""

    code: str  # 形如 "app.codename"
    category: str  # 所属业务大类
    resource: str  # 资源名称（中文）
    action: str  # 动作（中文）
    admin_only: bool = False  # 是否仅管理员组默认拥有
    user_default: bool = False  # 是否默认分配给普通用户


# =============================
# 权限清单（按业务模块梳理）
# =============================
PERMISSIONS: Tuple[PermissionDef, ...] = (
    # 账户与认证
    PermissionDef("accounts.view_user", "账户管理", "用户", "查看用户", user_default=True),
    PermissionDef("accounts.manage_user", "账户管理", "用户", "管理用户", admin_only=True),
    PermissionDef("accounts.manage_manager", "账户管理", "管理员", "管理员管理", admin_only=True),
    PermissionDef("accounts.manage_mail_account", "账户管理", "发信账号", "发信账号管理", admin_only=True),
    PermissionDef("auth.manage_group", "认证与授权", "权限组", "组管理", admin_only=True),

    # 赛事
    PermissionDef("contests.view_contest", "赛事管理", "比赛", "查看比赛", user_default=True),
    PermissionDef("contests.manage_contest", "赛事管理", "比赛", "管理比赛", admin_only=True),
    PermissionDef("contests.manage_team", "赛事管理", "战队", "战队管理"),
    PermissionDef("contests.manage_announcement", "赛事管理", "公告", "公告管理", admin_only=True),
    PermissionDef("contests.view_scoreboard", "赛事管理", "排行榜", "查看排行榜", user_default=True),
    PermissionDef("contests.export_contest_data", "赛事管理", "比赛数据", "导出比赛数据", admin_only=True),

    # 战队（轻量占位，视图已使用 teams.*，便于后续扩展独立权限）
    PermissionDef("teams.view_team", "赛事管理", "战队", "查看战队", user_default=True),
    PermissionDef("teams.manage_team", "赛事管理", "战队", "管理战队", user_default=True),
    PermissionDef("teams.join_team", "赛事管理", "战队", "加入战队", user_default=True),
    PermissionDef("teams.leave_team", "赛事管理", "战队", "退出战队", user_default=True),

    # 题目（比赛）
    PermissionDef("challenges.view_contest_challenge", "题目管理", "比赛题目", "查看题目", user_default=True),
    PermissionDef("challenges.manage_contest_challenge", "题目管理", "比赛题目", "管理题目", admin_only=True),
    PermissionDef("challenges.manage_contest_attachment", "题目管理", "比赛题目", "上传附件", admin_only=True),
    PermissionDef("challenges.download_contest_attachment", "题目管理", "比赛题目", "下载附件", user_default=True),
    PermissionDef("challenges.manage_contest_hint", "题目管理", "比赛题目", "提示管理", admin_only=True),
    PermissionDef("challenges.view_contest_submission", "题目管理", "比赛题目", "查看提交"),
    PermissionDef("challenges.submit_contest_flag", "题目管理", "比赛题目", "提交 Flag", user_default=True),

    # 题目（题库）
    PermissionDef("problem_bank.view_bank", "题库管理", "题库", "查看题库", user_default=True),
    PermissionDef("problem_bank.manage_bank", "题库管理", "题库", "管理题库", admin_only=True),
    PermissionDef("problem_bank.manage_bank_challenge", "题库管理", "题库题目", "管理题目", admin_only=True),
    PermissionDef("problem_bank.import_bank", "题库管理", "题库", "题库导入", admin_only=True),
    PermissionDef("problem_bank.export_bank", "题库管理", "题库", "题库导出", admin_only=True),
    PermissionDef("problem_bank.submit_bank_flag", "题库管理", "题库题目", "提交 Flag", user_default=True),

    # 提交计分
    PermissionDef("submissions.view_submission", "提交计分", "提交记录", "查看提交", user_default=True),

    # 通知
    PermissionDef("notifications.view_notification", "系统通知", "通知", "查看通知", user_default=True),

    # 靶机
    PermissionDef("machines.view_machine", "靶机管理", "靶机实例", "查看实例", user_default=True),
    PermissionDef("machines.start_machine", "靶机管理", "靶机实例", "启动实例", user_default=True),
    PermissionDef("machines.stop_machine", "靶机管理", "靶机实例", "停止实例", user_default=True),
    PermissionDef("machines.manage_machine", "靶机管理", "靶机实例", "管理实例", admin_only=True),

    # 系统
    PermissionDef("system.view_log", "系统审计", "系统日志", "查看日志", admin_only=True),
    PermissionDef("system.export_log", "系统审计", "系统日志", "导出日志", admin_only=True),
    PermissionDef("system.manage_config", "系统配置", "运行参数", "配置管理", admin_only=True),
)

# =============================
# manage 包含规则与工具
# =============================
def _build_implied_map(perms: Iterable[PermissionDef]) -> Dict[str, Set[str]]:
    """
    生成 manage 权限 -> 被包含的权限集合
    规则：manage_xxx 包含 codename 中包含 xxx 的其他权限
    """
    codes = [p.code for p in perms]
    implied: Dict[str, Set[str]] = {}
    for code in codes:
        if ".manage_" not in code:
            continue
        _, codename = code.split(".", 1)
        suffix = codename[len("manage_"): ]
        implied_set: Set[str] = set()
        for target in codes:
            if target == code:
                continue
            _, t_code = target.split(".", 1)
            if suffix and suffix in t_code:
                implied_set.add(target)
            if suffix and t_code.endswith(suffix):
                implied_set.add(target)
        implied[code] = implied_set
    return implied


IMPLIED_PERMISSIONS: Dict[str, Set[str]] = _build_implied_map(PERMISSIONS)


def expand_with_implied(perms: Iterable[str]) -> Set[str]:
    """根据 manage 包含规则递归展开权限集合"""
    expanded: Set[str] = set(perms)
    changed = True
    while changed:
        changed = False
        for code in list(expanded):
            implied = IMPLIED_PERMISSIONS.get(code, set())
            for target in implied:
                if target not in expanded:
                    expanded.add(target)
                    changed = True
    return expanded


# =============================
# 默认组与标签
# =============================
DEFAULT_ADMIN_GROUP = "Admins::Default"
DEFAULT_USER_GROUP = "Users::Default"


def _default_admin() -> Set[str]:
    return expand_with_implied(p.code for p in PERMISSIONS)


def _default_user() -> Set[str]:
    base = [p.code for p in PERMISSIONS if p.user_default]
    return expand_with_implied(base)


DEFAULT_ADMIN_GROUP_PERMS: Set[str] = _default_admin()
DEFAULT_USER_GROUP_PERMS: Set[str] = _default_user()
