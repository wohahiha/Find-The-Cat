"""
通用权限封装（apps.common.permissions）

职责：
- 放置全局可复用的权限类（基于 Django/DRF 的认证系统）
- 封装“登录/管理员/只读/资源 Owner/本人/队长”等常见场景的权限校验
- 出错时统一抛出 BizError 子类（PermissionDeniedError），由全局异常处理器统一包装响应
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from django.contrib.auth import get_user_model

from apps.auth.group import assign_default_group, sync_builtin_groups

from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.request import Request

from .exceptions import PermissionDeniedError

User = get_user_model()

# 确保内置权限/组在进程启动后同步一次，避免新增权限未下发到默认组
_GROUPS_SYNCED = False

def _ensure_groups_synced() -> None:
    global _GROUPS_SYNCED
    if _GROUPS_SYNCED:
        return
    sync_builtin_groups()
    _GROUPS_SYNCED = True


# ======================
# 小工具
# ======================

def _ensure_authenticated(request: Request) -> User:
    """
    确保用户已登录，返回 User；否则抛 PermissionDeniedError
    - 业务场景：所有权限类复用，统一登录态校验与错误提示
    """
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        # 不用 HTTP 401，而是业务层权限错误，由异常处理器决定返回格式
        raise PermissionDeniedError(message="请先登录后再执行此操作")
    return user


def has_biz_permission(user: User, perm: str) -> bool:
    """
    业务权限校验：
    - 支持 manage_ 前缀包含规则：拥有 manage_xxx 可包含所有包含 xxx 的权限
    - 超级管理员/Staff 兜底放行
    - perm 形如 "app.codename"
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    # staff 兜底：视为拥有所有权限，保持原有管理员体验
    if getattr(user, "is_staff", False):
        return True

    if "." not in perm:
        return False
    app_label, codename = perm.split(".", 1)

    # 直接命中
    if user.has_perm(perm):
        return True

    # manage_* 包含规则：持有 manage_xxx 即包含所有包含 xxx 的权限
    holder_perms = user.get_all_permissions()
    for p in holder_perms:
        try:
            holder_app, holder_code = p.split(".", 1)
        except ValueError:
            continue
        if holder_code.startswith("manage_"):
            suffix = holder_code[len("manage_"):]
            if suffix and suffix in codename:
                return True
            if suffix and codename.endswith(suffix):
                return True
        # 同 app 下的 manage 通配
        if holder_app == app_label and holder_code == "manage_contests" and "contest" in codename:
            return True
        if holder_app == app_label and holder_code == "manage_bank_challenges" and "bank_challenge" in codename:
            return True
    return False


def ensure_biz_permission(user: User, perm: str) -> None:
    """不满足权限时抛出业务无权异常"""
    if not has_biz_permission(user, perm):
        raise PermissionDeniedError(message=f"无权执行操作：{perm}")


class BizPermission(BasePermission):
    """
    基于业务权限 code 的通用权限类

    用法：
    - 在视图类上声明 biz_permission（单个权限）或 biz_permission_map（按 action/method 映射）
    - 没有声明时不拦截
    """

    message = "无权执行当前操作"

    @staticmethod
    def _get_perm(request: Request, view: Any) -> Optional[str]:
        # 优先使用 biz_permission_map：ViewSet 使用 action，APIView 使用 HTTP method
        if hasattr(view, "biz_permission_map"):
            mapping: Dict[str, str] = getattr(view, "biz_permission_map", {})
            key = getattr(view, "action", None) or request.method.lower()
            return mapping.get(key)
        # 其次使用单个 biz_permission
        return getattr(view, "biz_permission", None)

    def has_permission(self, request: Request, view: Any) -> bool:
        _ensure_groups_synced()
        user = _ensure_authenticated(request)
        # 若用户尚未绑定任何组，则自动加入默认组（区分管理员/普通用户），避免权限缺失
        if not user.groups.exists():
            assign_default_group(user, is_admin=getattr(user, "is_staff", False))
        perm = self._get_perm(request, view)
        if not perm:
            return True
        ensure_biz_permission(user, perm)
        return True


# ======================
# 通用权限类
# ======================

class AllowAny(BasePermission):
    """
    允许任何请求通过（公开接口）
    """

    def has_permission(self, request: Request, view: Any) -> bool:  # noqa: D401
        return True


class IsAuthenticated(BasePermission):
    """
    需要已登录用户

    等价于 DRF 默认的 IsAuthenticated，但出错时抛 BizError，
    便于全局异常处理器统一格式
    """

    message = "请先登录后再执行此操作"

    def has_permission(self, request: Request, view: Any) -> bool:
        _ensure_authenticated(request)
        return True


class IsAdmin(BasePermission):
    """
    需要管理员权限（is_staff == True）

    - 未登录 → 提示先登录
    - 已登录但非 staff → 无权访问
    """

    message = "仅管理员可以执行此操作"

    def has_permission(self, request: Request, view: Any) -> bool:
        user = _ensure_authenticated(request)

        if user.is_staff:
            return True

        raise PermissionDeniedError(message=self.message)


class IsSuperUser(BasePermission):
    """
    需要超级管理员权限（is_superuser == True）
    """

    message = "仅超级管理员可以执行此操作"

    def has_permission(self, request: Request, view: Any) -> bool:
        user = _ensure_authenticated(request)

        if user.is_superuser:
            return True

        raise PermissionDeniedError(message=self.message)


class ReadOnly(BasePermission):
    """
    所有用户都可以访问，但仅允许安全方法（GET / HEAD / OPTIONS）

    适合用在“公开只读接口”（如公开题目列表、公告等）
    """

    message = "该接口仅支持只读操作"

    def has_permission(self, request: Request, view: Any) -> bool:
        return request.method in SAFE_METHODS


class IsAdminOrReadOnly(BasePermission):
    """
    只读放行，非只读操作需管理员权限

    适用于 GET 公开但写操作仅管理员可用的接口，统一避免视图内手写判断
    """

    message = "仅管理员可以执行此操作"

    def has_permission(self, request: Request, view: Any) -> bool:
        if request.method in SAFE_METHODS:
            return True
        user = _ensure_authenticated(request)
        if user.is_staff:
            return True
        raise PermissionDeniedError(message=self.message)


class IsOwner(BasePermission):
    """
    题目 Owner（出题者）
    - 用于 Challenge、ChallengeTask 等
    - 不包含管理员逻辑
    """

    message = "你不是该资源的 Owner"

    # 对出题者的称呼，允许后期修改：creator / author / ...
    owner_attr: str = "owner"

    def has_permission(self, request: Request, view: Any) -> bool:
        # 先保证是登录用户
        _ensure_authenticated(request)
        return True

    def has_object_permission(self, request: Request, view: Any, obj: Any) -> bool:
        user = _ensure_authenticated(request)

        # 拿到所有者
        owner = getattr(obj, self.owner_attr, None)

        # owner 应当是 User
        if isinstance(owner, User) and owner.pk == user.pk:
            return True

        # 不是 owner，一律拒绝
        raise PermissionDeniedError(message=self.message)


class IsOwnerOrAdmin(BasePermission):
    """
    资源所有者或管理员均可访问

    - 优先判定管理员（便于后台代办）
    - 否则回退到 Owner 校验，保证个人资源安全
    """

    message = "仅资源所有者或管理员可执行此操作"

    def has_permission(self, request: Request, view: Any) -> bool:
        # 先保证登录，再允许管理员提前放行
        user = _ensure_authenticated(request)
        if user.is_staff:
            return True
        return True

    def has_object_permission(self, request: Request, view: Any, obj: Any) -> bool:
        user = _ensure_authenticated(request)
        if user.is_staff:
            return True
        return IsOwner().has_object_permission(request, view, obj)


class IsSelf(BasePermission):
    """
    只允许“自己访问自己”的场景

    典型用法：
    - /api/users/<id>/ 获取/修改个人信息
    - 对象是 User 或者含有 user 字段的模型
    """

    message = "仅本人可以访问该资源"

    def has_permission(self, request: Request, view: Any) -> bool:
        # 先保证是登录用户
        _ensure_authenticated(request)
        return True

    def has_object_permission(self, request: Request, view: Any, obj: Any) -> bool:
        user = _ensure_authenticated(request)

        target_user: User | None = None

        # 情况 A：对象本身就是 User
        if isinstance(obj, User):
            target_user = obj
        # 情况 B：对象不是 User，但包含 user 字段
        elif hasattr(obj, "user"):
            maybe_user = getattr(obj, "user")
            if isinstance(maybe_user, User):
                target_user = maybe_user

        if target_user is None:
            # 没拿到 user，直接拒绝
            raise PermissionDeniedError(message="无权访问该资源")

        if target_user.pk == user.pk:
            return True

        raise PermissionDeniedError(message=self.message)


class IsLeader(BasePermission):
    """
    队长权限（基于 Team.captain 字段判断）

    适用对象：
    - 对象本身是 Team：
        - obj.captain == request.user → 允许
    - 对象含 team 字段（常见于 Submission、Solve、MachineInstance 等）：
        - obj.team.captain == request.user → 允许
    - 否则 → 拒绝

    要求：
    - Team 模型包含字段： captain = models.ForeignKey(User, ...)
    """

    message = "仅队长可执行此操作"

    # 对队长的称呼，允许后期修改：leader / ...
    leader_attr: str = "captain"

    def has_permission(self, request: Request, view: Any) -> bool:
        # 先保证是登录用户
        _ensure_authenticated(request)
        return True

    def has_object_permission(self, request: Request, view: Any, obj: Any) -> bool:
        user = _ensure_authenticated(request)

        # 把可能承载“队伍信息”的对象列出来：
        # 情况 1：对象本身就是 Team
        # 情况 2：对象不是 Team，而是“属于某个 Team 的资源”（典型：Submission、Solve、MachineInstance 等）
        candidates = [obj, getattr(obj, "team", None)]

        for target in candidates:
            if target is None:
                continue

            if hasattr(target, self.leader_attr):
                captain = getattr(target, self.leader_attr, None)

                # captain 必须是 User 且与当前用户 pk 一致
                if isinstance(captain, User) and captain.pk == user.pk:
                    return True

                # 找到了 captain 但不是当前用户 → 直接无权限
                raise PermissionDeniedError(message=self.message)

        # 完全没有 captain 信息，也视为无权限
        raise PermissionDeniedError(message=self.message)
