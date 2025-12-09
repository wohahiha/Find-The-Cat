# apps/challenges/attachment_service.py

from __future__ import annotations

from apps.common.base.base_service import BaseService
from apps.common.exceptions import ValidationError
from apps.common.infra.file_storage import default_storage

from .schemas import AttachmentUploadSchema


class AttachmentUploadService(BaseService[dict]):
    """
    题目附件上传服务：
    - 业务场景：管理员上传题目附件，存储并返回可访问 URL
    - 模块角色：封装存储逻辑，按比赛/题目标识组织子目录
    """

    atomic_enabled = False

    def perform(self, schema: AttachmentUploadSchema, *, content: bytes) -> dict:
        # 限制文件大小与类型，防止滥用存储
        max_size = 10 * 1024 * 1024  # 10MB
        if len(content) > max_size:
            raise ValidationError(message="附件过大，单个文件请控制在 10MB 内")
        allowed_suffix = {".zip", ".rar", ".tar", ".tar.gz", ".gz", ".tgz", ".bz2", ".7z", ".txt", ".pdf", ".md", ".json"}
        lower_name = schema.filename.lower()
        if lower_name.endswith(".tar.gz"):
            suffix = ".tar.gz"
        elif "." in lower_name:
            suffix = "." + lower_name.split(".")[-1]
        else:
            suffix = ""
        if suffix and suffix not in allowed_suffix:
            raise ValidationError(message="不支持的附件类型，请打包为 zip/tar 或提供文本类文件")
        parts = ["attachments"]
        if schema.contest_slug:
            parts.append(schema.contest_slug)
        if schema.challenge_slug:
            parts.append(schema.challenge_slug)
        subdir = "/".join(parts)
        relative_path, url = default_storage.save_bytes(content=content, filename=schema.filename, subdir=subdir)
        return {"path": relative_path, "url": url}
