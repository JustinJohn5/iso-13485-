"""文件集审查 API 合同；可校正提取线索，禁止任意扩展字段。"""
from datetime import date
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from App.Services.DocumentControl.Metadata import normalize_number


class MetadataOverride(BaseModel):
    model_config = ConfigDict(extra='forbid')
    number: str = Field(default='', max_length=64)
    revision: str = Field(default='', max_length=32)
    effective_date: str = Field(default='', max_length=10)
    category: Literal['policy', 'manual', 'required', 'organization', 'regulatory', 'unclassified'] = 'unclassified'
    layer: Literal['document', 'template', 'record', 'unknown'] = 'unknown'
    status: Literal['unknown', 'controlled', 'draft', 'obsolete'] = 'unknown'

    @field_validator('number')
    @classmethod
    def number_valid(cls, value):
        value = normalize_number(value)
        if value and not re.fullmatch(r'[A-Z0-9][A-Z0-9._/-]{1,63}', value):
            raise ValueError('编号仅支持字母、数字与 . _ / -')
        return value

    @field_validator('effective_date')
    @classmethod
    def date_valid(cls, value):
        if value:
            return date.fromisoformat(value).isoformat()
        return value


class ReviewCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    file_uids: list[str] = Field(min_length=1, max_length=20)
    as_of_date: date
    overrides: dict[str, MetadataOverride] = Field(default_factory=dict, max_length=20)


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int = Field(ge=1)
    kind: Literal['version', 'requirement']
    issue_id: str = Field(min_length=1, max_length=64)
    file_uid: str = Field(min_length=1, max_length=36)
    reason: str = Field(min_length=5, max_length=500)

    @field_validator('reason')
    @classmethod
    def reason_valid(cls, value):
        if len(value.strip()) < 5:
            raise ValueError('请填写至少5字的确认依据')
        return value.strip()
