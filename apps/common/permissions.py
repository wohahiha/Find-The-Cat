"""
通用权限封装（apps.common.permissions）

职责：
- 放置全局可复用的权限类（基于 Django/DRF 的认证系统）；
- 封装“登录 / 管理员 / 只读 / 题目 Owner / 自己 / 队长”等常见场景；
- 出错时统一抛出 BizError 子类（PermissionDeniedError），
  由全局异常处理器统一包装成标准响应结构。
"""

from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model

from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.request import Request

from .exceptions import PermissionDeniedError

User = get_user_model()


# ======================
# 小工具
# ======================

def _ensure_authenticated(request: Request) -> User:
    """
    确保用户已登录，返回 User；否则抛 PermissionDeniedError。
    """
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        # 不用 HTTP 401，而是业务层权限错误，由异常处理器决定返回格式
        raise PermissionDeniedError(message="请先登录后再执行此操作")
    return user


# ======================
# 通用权限类
# ======================

class IsAuthenticated(BasePermission):
    """
    需要已登录用户。

    等价于 DRF 默认的 IsAuthenticated，但出错时抛 BizError，
    便于全局异常处理器统一格式。
    """

    message = "请先登录后再执行此操作"

    def has_permission(self, request: Request, view: Any) -> bool:
        _ensure_authenticated(request)
        return True


class IsAdmin(BasePermission):
    """
    需要管理员权限（is_staff == True）。

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
    需要超级管理员权限（is_superuser == True）。
    """

    message = "仅超级管理员可以执行此操作"

    def has_permission(self, request: Request, view: Any) -> bool:
        user = _ensure_authenticated(request)

        if user.is_superuser:
            return True

        raise PermissionDeniedError(message=self.message)


class ReadOnly(BasePermission):
    """
    所有用户都可以访问，但仅允许安全方法（GET / HEAD / OPTIONS）。

    适合用在“公开只读接口”（如公开题目列表、公告等）。
    """

    message = "该接口仅支持只读操作"

    def has_permission(self, request: Request, view: Any) -> bool:
        return request.method in SAFE_METHODS


class IsOwner(BasePermission):
    """
    题目 Owner（出题者）
    - 用于 Challenge、ChallengeTask 等
    - 不包含管理员逻辑
    """

    message = "你不是该资源的 Owner。"

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


class IsSelf(BasePermission):
    """
    只允许“自己访问自己”的场景。

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
    队长权限（基于 Team.captain 字段判断）。

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
