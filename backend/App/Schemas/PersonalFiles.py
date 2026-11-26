"""个人分组名称及批量成员输入约束。"""
import re
import unicodedata

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GroupName(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=120)

    @field_validator('name')
    @classmethod
    def clean_name(cls, value: str) -> str:
        if re.search(r'[\x00-\x1f\x7f]', value):
            raise ValueError('分组名称不能包含控制字符或换行')
        value = unicodedata.normalize('NFKC', value).strip()
        if not value or len(value) > 120:
            raise ValueError('请输入1至120字的分组名称')
        return value


class GroupMembers(BaseModel):
    model_config = ConfigDict(extra='forbid')
    file_uids: list[str] = Field(min_length=1, max_length=100)

    @field_validator('file_uids')
    @classmethod
    def valid_uids(cls, values: list[str]) -> list[str]:
        if any(not value.strip() or len(value) > 36 or value != value.strip() for value in values):
            raise ValueError('文件标识不能为空或超出长度限制')
        if len(set(values)) != len(values):
            raise ValueError('请提交不重复的文件标识')
        return values
