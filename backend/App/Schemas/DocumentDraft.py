"""文档编写接口合同。"""
from pydantic import BaseModel, ConfigDict, Field, field_validator


class DraftCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    template_id: str = Field(min_length=1, max_length=64)
    parameters: dict[str, str] = Field(max_length=20)


class DraftUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int = Field(ge=1)
    parameters: dict[str, str] | None = Field(default=None, max_length=20)
    sections: dict[str, str] | None = Field(default=None, max_length=20)
    reason: str = Field(min_length=5, max_length=500)

    @field_validator('reason')
    @classmethod
    def reason_valid(cls, value):
        if len(value.strip()) < 5:
            raise ValueError('请填写至少5字的变更原因')
        return value.strip()
