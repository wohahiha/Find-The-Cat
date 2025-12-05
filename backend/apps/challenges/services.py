"""
挑战服务聚合模块：对外导出题目相关的业务服务
- ChallengeCreateService / ChallengeUpdateService：题目 CRUD 与子任务/附件/提示同步
- ChallengeHintService：提示列表与解锁
- AttachmentUploadService：附件上传
"""

from __future__ import annotations

from .crud_service import ChallengeCreateService, ChallengeUpdateService
from .hint_service import ChallengeHintService
from .attachment_service import AttachmentUploadService

# 对外导出服务列表
__all__ = [
    "ChallengeCreateService",  # 题目创建服务
    "ChallengeUpdateService",  # 题目更新服务
    "ChallengeHintService",  # 题目提示服务
    "AttachmentUploadService",  # 附件上传服务
]
