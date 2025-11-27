"""
通用加解密与散列工具

- 提供哈希、HMAC 及随机令牌生成，统一用于签名/验证码等场景
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Union


def sha256(text: str) -> str:
    """计算字符串的 SHA256 摘要，常用于签名/校验"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def hmac_sha256(key: Union[str, bytes], msg: Union[str, bytes]) -> str:
    """
    计算 HMAC-SHA256：
    - key 与 msg 支持 str/bytes，内部统一转为 bytes
    - 业务场景：签名生成、接口校验等
    """
    if isinstance(key, str):
        key = key.encode("utf-8")
    if isinstance(msg, str):
        msg = msg.encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def random_token(length: int = 32) -> str:
    """
    生成随机字符串（hex），默认 32 字符
    - 业务场景：生成验证码种子、一次性 token 等
    """
    return secrets.token_hex(length // 2)
