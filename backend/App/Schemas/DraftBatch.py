"""显式选择草稿的批量参数联动合同。"""
from pydantic import BaseModel, ConfigDict, Field, field_validator

from App.Schemas.DocumentDraft import DraftUpdate


class DraftSelection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    draft_uid: str = Field(min_length=1, max_length=36)
    revision: int = Field(ge=1)


class DraftBatchChange(BaseModel):
    model_config = ConfigDict(extra='forbid')
    drafts: list[DraftSelection] = Field(min_length=1, max_length=20)
    parameters: dict[str, str] = Field(min_length=1, max_length=4)
    reason: str = Field(min_length=5, max_length=500)

    @field_validator('parameters')
    @classmethod
    def shared_fields_only(cls, value):
        if not set(value).issubset({'company', 'project', 'product', 'model'}):
            raise ValueError('仅组织、项目、产品及型号可跨草稿联动，编号及文件版本分别管理')
        return value

    @field_validator('reason')
    @classmethod
    def reason_valid(cls, value):
        return DraftUpdate.reason_valid(value)
