# apps/challenges/services.py

from __future__ import annotations

"""
挑战服务聚合模块：对外导出题目相关的业务服务。
- ChallengeCreateService / ChallengeUpdateService：题目 CRUD 与子任务/附件/提示同步。
- ChallengeHintService：提示列表与解锁。
- AttachmentUploadService：附件上传。
"""

from .crud_service import ChallengeCreateService, ChallengeUpdateService
from .hint_service import ChallengeHintService
from .attachment_service import AttachmentUploadService

__all__ = [
    "ChallengeCreateService",
    "ChallengeUpdateService",
    "ChallengeHintService",
    "AttachmentUploadService",
]
