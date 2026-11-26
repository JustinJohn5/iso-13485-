"""AI 文件审阅接口输入结构。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AiReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["evidence_search", "semantic_review"]
    rule_id: str = Field(min_length=1, max_length=80)
    file_uid: str = Field(min_length=1, max_length=36)


class AiReviewDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["accepted", "accepted_edited", "rejected"]
    note: str = Field(min_length=1, max_length=1000)
    edited_result: str = Field(default="", max_length=12000)

    @field_validator("note")
    @classmethod
    def note_must_have_content(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("决定理由不能为空")
        return cleaned

    @field_validator("edited_result")
    @classmethod
    def edited_result_must_be_text(cls, value: str) -> str:
        return value.strip()
