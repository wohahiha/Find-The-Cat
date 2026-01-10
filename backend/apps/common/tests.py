# -*- coding: utf-8 -*-
"""
公共模块安全校验单测：
- 上传文件校验（类型/大小）
"""

from __future__ import annotations

from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.common.utils.validators import validate_upload_file
from apps.common.exceptions import ValidationError


class UploadValidatorTests(TestCase):
    """校验上传文件的类型/大小限制"""

    def test_invalid_content_type_should_fail(self):
        bad = SimpleUploadedFile("bad.exe", b"hello", content_type="application/x-msdownload")
        with self.assertRaises(ValidationError):
            validate_upload_file(
                bad,
                allowed_content_types={"application/zip"},
                allowed_suffixes={".zip"},
                max_size_mb=1,
                field_name="附件",
            )

    def test_exceed_size_should_fail(self):
        big = SimpleUploadedFile("big.zip", b"a" * (2 * 1024 * 1024 + 1), content_type="application/zip")
        with self.assertRaises(ValidationError):
            validate_upload_file(
                big,
                allowed_content_types={"application/zip"},
                allowed_suffixes={".zip"},
                max_size_mb=2,
                field_name="附件",
            )

    def test_valid_upload_should_pass(self):
        ok = SimpleUploadedFile("ok.zip", b"abc", content_type="application/zip")
        # 不应抛出异常
        validate_upload_file(
            ok,
            allowed_content_types={"application/zip"},
            allowed_suffixes={".zip"},
            max_size_mb=2,
            field_name="附件",
        )
