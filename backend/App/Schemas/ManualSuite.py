"""整套手册 API 输入合同。"""
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

from App.Services.ManualSuites.Content import clean_value


class SuiteCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=32)

    @field_validator('name', 'version')
    @classmethod
    def value_valid(cls, value):
        return clean_value(value)


class SuiteMutation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int = Field(ge=1)


class SuiteGenerate(SuiteMutation):
    catalog_keys: list[str] = Field(min_length=1, max_length=100)
    parameters: dict[str, str] = Field(max_length=5)


class SuiteImport(SuiteMutation):
    file_uids: list[str] = Field(min_length=1, max_length=100)


class SuiteItemUpdate(SuiteMutation):
    catalog_key: str = Field(max_length=64)
    file_version: str = Field(max_length=32)
    sections: dict[str, str] | None = Field(default=None, max_length=20)
    reason: str = Field(default='', max_length=500)


class SuiteInspection(SuiteMutation):
    as_of_date: date
