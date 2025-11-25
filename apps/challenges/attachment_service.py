# apps/challenges/attachment_service.py

from __future__ import annotations

from apps.common.base.base_service import BaseService
from apps.common.infra.file_storage import default_storage

from .schemas import AttachmentUploadSchema


class AttachmentUploadService(BaseService[dict]):
    """
    题目附件上传服务：
    - 业务场景：管理员上传题目附件，存储并返回可访问 URL。
    - 模块角色：封装存储逻辑，按比赛/题目标识组织子目录。
    """

    atomic_enabled = False

    def perform(self, schema: AttachmentUploadSchema, *, content: bytes) -> dict:
        parts = ["attachments"]
        if schema.contest_slug:
            parts.append(schema.contest_slug)
        if schema.challenge_slug:
            parts.append(schema.challenge_slug)
        subdir = "/".join(parts)
        relative_path, url = default_storage.save_bytes(content=content, filename=schema.filename, subdir=subdir)
        return {"path": relative_path, "url": url}
