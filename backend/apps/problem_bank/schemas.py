from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar, List, Optional

from apps.common.base.base_schema import BaseSchema
from apps.common.exceptions import ValidationError
from apps.common.utils.validators import validate_slug


@dataclass
class ProblemBankCreateSchema(BaseSchema[None]):
    """创建题库入参：仅管理员使用"""

    auto_validate: ClassVar[bool] = True
    name: str
    slug: str
    description: str = ""
    is_public: bool = False

    def validate(self) -> None:
        if not self.name:
            raise ValidationError(message="题库名称不能为空")
        if not self.slug:
            raise ValidationError(message="题库标识不能为空")
        validate_slug(self.slug)


@dataclass
class ProblemBankUpdateSchema(BaseSchema[None]):
    """更新题库入参：支持部分字段"""

    auto_validate: ClassVar[bool] = True
    bank_slug: str
    name: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None

    def validate(self) -> None:
        if not self.bank_slug:
            raise ValidationError(message="请提供题库标识")
        if self.name is not None and not self.name.strip():
            raise ValidationError(message="题库名称不能为空")


@dataclass
class BankImportFromContestSchema(BaseSchema[None]):
    """从比赛导入全部题目入参：需先选定题库（slug）"""

    auto_validate: ClassVar[bool] = True
    contest_slug: str
    bank_slug: str

    def validate(self) -> None:
        if not self.contest_slug:
            raise ValidationError(message="请提供比赛标识")
        if not self.bank_slug:
            raise ValidationError(message="请提供题库标识")


@dataclass
class BankImportChallengesSchema(BaseSchema[None]):
    """从比赛指定题目导入：需先选定题库"""

    auto_validate: ClassVar[bool] = True
    bank_slug: str
    challenge_slugs: List[str] = field(default_factory=list)
    contest_slug: Optional[str] = None

    def validate(self) -> None:
        if not self.challenge_slugs:
            raise ValidationError(message="请选择需要导入的题目")
        if not self.bank_slug:
            raise ValidationError(message="请提供题库标识")


@dataclass
class BankExternalImportSchema(BaseSchema[None]):
    """外部 zip 导入题库入参：需先选定题库"""

    auto_validate: ClassVar[bool] = True
    bank_slug: str
    filename: str

    def validate(self) -> None:
        if not self.filename:
            raise ValidationError(message="缺少文件名")
        if not self.bank_slug:
            raise ValidationError(message="请提供题库标识")


@dataclass
class BankExportSchema(BaseSchema[None]):
    """导出题库入参：基于题库 slug"""

    auto_validate: ClassVar[bool] = True
    bank_slug: str

    def validate(self) -> None:
        if not self.bank_slug:
            raise ValidationError(message="缺少题库标识")


@dataclass
class BankChallengeSubmitSchema(BaseSchema[None]):
    """题库作答入参：仅需 Flag"""

    auto_validate: ClassVar[bool] = True
    flag: str

    def validate(self) -> None:
        if not self.flag:
            raise ValidationError(message="请输入 Flag")
        if len(self.flag) > 1024:
            raise ValidationError(message="提交内容过长")


@dataclass
class BankChallengeUpdateSchema(BaseSchema[None]):
    """更新题库题目入参：支持部分字段"""

    auto_validate: ClassVar[bool] = True
    bank_slug: str
    challenge_slug: str
    title: Optional[str] = None
    short_description: Optional[str] = None
    content: Optional[str] = None
    difficulty: Optional[str] = None
    flag: Optional[str] = None
    flag_type: Optional[str] = None
    dynamic_prefix: Optional[str] = None
    flag_case_insensitive: Optional[bool] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None

    def validate(self) -> None:
        if not self.bank_slug:
            raise ValidationError(message="缺少题库标识")
        if not self.challenge_slug:
            raise ValidationError(message="缺少题目标识")
        if self.flag_type and self.flag_type not in {"static", "dynamic"}:
            raise ValidationError(message="Flag 类型仅支持 static/dynamic")
        if self.difficulty and self.difficulty not in {"easy", "medium", "hard"}:
            raise ValidationError(message="难度仅支持 easy/medium/hard")
