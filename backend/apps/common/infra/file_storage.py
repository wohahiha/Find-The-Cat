"""
文件存储封装（本地+OSS 可切换）

- 默认将文件保存到 MEDIA_ROOT，返回相对路径与访问 URL
- 预留 OSS 封装，方便切换对象存储，不影响调用方
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Tuple

from django.conf import settings
from apps.common.exceptions import StorageUnavailableError
from apps.common.infra.logger import get_logger

logger = get_logger(__name__)

try:
    import boto3  # type: ignore
    from botocore.exceptions import BotoCoreError, ClientError  # type: ignore
except Exception:  # pragma: no cover
    boto3 = None
    BotoCoreError = ClientError = Exception


class LocalFileStorage:
    """
    本地文件存储
    - save_bytes: 将字节内容写入 MEDIA_ROOT/子目录，返回相对路径与 URL
    """

    def __init__(self, base_dir: str | None = None):
        # 基础目录：默认 MEDIA_ROOT
        media_root = getattr(settings, "MEDIA_ROOT", None)
        self.base_dir = Path(base_dir or media_root or "uploads").resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_bytes(self, *, content: bytes, filename: str, subdir: str | None = None) -> Tuple[str, str | None]:
        """
        保存二进制内容到本地磁盘

        入参：
        - content: 文件字节内容
        - filename: 文件名（会直接用于存储路径，调用方需保证安全性）
        - subdir: 可选子目录，便于分类存储

        返回：
        - relative_path: 相对于 base_dir 的存储路径（字符串）
        - url: 若配置 MEDIA_URL，则返回可访问的 URL，否则为 None
        """
        safe_name = _safe_filename(filename)
        safe_subdir = _safe_subdir(subdir)
        try:
            target_dir = self.base_dir / safe_subdir if safe_subdir else self.base_dir
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / safe_name
            target_path.write_bytes(content)

            relative_path = str(target_path.relative_to(self.base_dir))
            media_url = getattr(settings, "MEDIA_URL", None)
            url = f"{media_url.rstrip('/')}/{relative_path}" if media_url else None
            return relative_path, url
        except Exception as exc:
            logger.exception("本地文件存储失败", extra={"filename": safe_name, "subdir": safe_subdir})
            raise StorageUnavailableError() from exc


class OSSStorage:
    """
    对象存储封装（S3/OSS 兼容）
    - 依赖 boto3，需在环境中配置 access key/secret/endpoint/bucket
    """

    def __init__(self):
        if not boto3:
            raise RuntimeError("未安装 boto3，无法使用 OSS 存储，请安装或切换 STORAGE_BACKEND=local")
        self.endpoint = os.getenv("OSS_ENDPOINT")
        self.access_key = os.getenv("OSS_ACCESS_KEY_ID")
        self.secret_key = os.getenv("OSS_ACCESS_KEY_SECRET")
        self.bucket = os.getenv("OSS_BUCKET")
        self.prefix = (os.getenv("OSS_KEY_PREFIX") or "").strip().strip("/")
        if not all([self.endpoint, self.access_key, self.secret_key, self.bucket]):
            raise RuntimeError(
                "OSS 配置不完整，请在 .env 中填写 OSS_ENDPOINT/OSS_ACCESS_KEY_ID/OSS_ACCESS_KEY_SECRET/OSS_BUCKET")
        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        )

    def save_bytes(self, *, content: bytes, filename: str, subdir: str | None = None) -> Tuple[str, str]:
        """
        上传文件到对象存储，返回 key 与可访问 URL（若 endpoint 支持）
        """
        safe_name = _safe_filename(filename)
        safe_subdir = _safe_subdir(subdir)
        key_parts = [p for p in [self.prefix, safe_subdir, safe_name] if p]
        key = "/".join(key_parts)
        try:
            self.client.put_object(Bucket=self.bucket, Key=key, Body=content)
        except (BotoCoreError, ClientError) as exc:  # pragma: no cover - 依赖外部服务
            logger.exception("上传 OSS 失败", extra={"bucket": self.bucket, "key": key})
            raise StorageUnavailableError() from exc
        # 访问 URL：直接拼接 endpoint/key，举办方可根据实际网关调整
        url = f"{self.endpoint.rstrip('/')}/{self.bucket}/{key}"
        return key, url


def get_storage():
    """
    根据环境变量选择存储后端：
    - STORAGE_BACKEND=oss：使用 OSSStorage
    - 默认：LocalFileStorage
    """
    backend = os.getenv("STORAGE_BACKEND", "local").lower()
    if backend == "oss":
        return OSSStorage()
    return LocalFileStorage()


# 便于直接导入使用
default_storage = get_storage()


def _safe_filename(filename: str) -> str:
    """
    生成安全文件名：去除路径片段并添加随机前缀，避免穿越/覆写
    """
    name = Path(filename or "").name.replace("\\", "").replace("/", "")
    if not name or name in {".", ".."}:
        name = "file"
    # 限制长度，避免文件系统报错
    name = name[-120:]
    prefix = secrets.token_hex(8)
    return f"{prefix}_{name}"


def _safe_subdir(subdir: str | None) -> str:
    """
    清洗子目录，剔除 .. / 空白，防止逃逸到媒体目录之外
    """
    if not subdir:
        return ""
    parts = []
    for part in str(subdir).replace("\\", "/").split("/"):
        if not part or part in {".", ".."}:
            continue
        parts.append(part)
    return "/".join(parts)
