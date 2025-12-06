from __future__ import annotations

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.plumbing import build_bearer_security_scheme_object
from drf_spectacular.openapi import AutoSchema
import re


class JWTAuthScheme(OpenApiAuthenticationExtension):
    """
    为自定义 JWTAuthentication 提供 OpenAPI 描述，文档中显示 Bearer Auth
    """
    target_class = "apps.common.authentication.JWTAuthentication"
    name = "JWTAuth"

    def get_security_definition(self, auto_schema):
        return build_bearer_security_scheme_object(
            header_name="Authorization",
            token_prefix="Bearer",
        )


class ShortDescriptionAutoSchema(AutoSchema):
    """
    自定义 AutoSchema：为缺少描述的接口填充简短中文说明
    - 优先使用父类生成的描述（extend_schema 或方法 docstring）
    - 其次取视图类 docstring 首行
    - 最后回退为“<METHOD> <path> 接口”
    """

    def get_description(self) -> str:
        desc = super().get_description()
        if desc:
            return desc
        doc = (getattr(self.view, "__doc__", "") or "").strip()
        if doc:
            first_line = doc.splitlines()[0].strip()
            if first_line:
                return first_line
        # 回退兜底：method + path 简述
        return f"{self.method} {self.path} 接口"

    def get_summary(self) -> str:
        summary = super().get_summary()
        if summary:
            return summary.replace("：", "")
        # 使用方法 docstring 首行作为摘要
        action_name = getattr(self.view, "action", None)
        method_obj = getattr(self.view, action_name, None) if action_name else getattr(self.view, self.method.lower(), None)
        if method_obj and method_obj.__doc__:
            first = method_obj.__doc__.strip().splitlines()[0].strip()
            if first:
                return first.replace("：", "")
        # 再用类 docstring 首行
        doc = (getattr(self.view, "__doc__", "") or "").strip()
        if doc:
            first = doc.splitlines()[0].strip()
            if first:
                return first.replace("：", "")
        # 兜底：METHOD + path
        return f"{self.method} {self.path}".replace("：", "")

    def get_tags(self):
        tags = super().get_tags() or []
        # 如果显式设置了且不是默认的 "api"/"accounts"，沿用
        if tags and tags not in (["api"], ["accounts"]):
            return tags
        # 默认按路径推导标签，如 /api/accounts/... -> accounts，支持 accounts 子域映射
        path = getattr(self, "path", "") or ""
        parts = [p for p in path.strip("/").split("/") if p]
        for part in parts:
            if part.lower() == "api":
                continue
            # 账户子域映射
            if part == "accounts" and len(parts) > 1:
                sub = parts[1]
                if sub == "auth":
                    if len(parts) > 2 and parts[2] == "password":
                        return ["accounts-password"]
                    return ["accounts-auth"]
                if sub == "email":
                    return ["accounts-email"]
                if sub == "me" or sub in {"avatar", "roles", "permissions"}:
                    return ["accounts-profile"]
            return [part.replace("-", "_")]
        return ["api"]


def _sanitize_operation_id(value: str) -> str:
    """简易清洗：非字母数字下划线替换为下划线"""
    return re.sub(r"[^0-9a-zA-Z_]", "_", value)


def build_operation_id(route, path: str, method: str, action: str | None) -> str:
    """
    自定义 operationId：避免冲突，基于 HTTP 方法 + 路径生成唯一值
    - 将 /api/contests/{contest_slug}/challenges/ 转为 contests_challenges_list
    - 路径参数 {x} 替换为 x
    """
    _ = route
    # 清理路径前缀和分隔符
    clean = path.strip("/").replace("api/", "")
    parts = []
    for part in clean.split("/"):
        if part.startswith("{") and part.endswith("}"):
            part = part[1:-1]
        if part:
            parts.append(part.replace("-", "_"))
    base = "_".join(parts) or "root"
    verb = method.lower()
    if action:
        op_id = f"{verb}_{base}_{action}"
    else:
        op_id = f"{verb}_{base}"
    return _sanitize_operation_id(op_id)
