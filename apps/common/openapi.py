from __future__ import annotations

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.plumbing import build_bearer_security_scheme_object

class JWTAuthScheme(OpenApiAuthenticationExtension):
    """
    为自定义 JWTAuthentication 提供 OpenAPI 描述，文档中显示 Bearer Auth。
    """
    target_class = "apps.common.authentication.JWTAuthentication"
    name = "JWTAuth"

    def get_security_definition(self, auto_schema):
        return build_bearer_security_scheme_object(
            header_name="Authorization",
            token_prefix="Bearer",
        )
