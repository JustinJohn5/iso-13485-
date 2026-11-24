"""预筛上下文：事实与不适用依据由用户提交，确认身份只由服务端冻结。"""
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from App.Utils.TimeUtils import now

FactKey = Literal['design', 'sterile', 'implant', 'installation', 'servicing', 'outsourcing',
                  'software', 'cleaning', 'process_validation', 'customer_property']
Purpose = Literal['auto', 'procedure', 'plan', 'instruction', 'report', 'form', 'record']


class ApplicabilityDecision(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    clause: str = Field(pattern=r'^[6-8](?:\.\d{1,2}){1,3}$', max_length=16)
    reason: str = Field(min_length=5, max_length=1000)
    basis: str = Field(min_length=5, max_length=1000)


class PrescreenContext(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    scope: Literal['documents', 'system'] = 'documents'
    scope_description: str = Field(default='', max_length=2000)
    as_of_date: date | None = None
    facts: dict[FactKey, Literal['yes', 'no', 'unknown']] = Field(default_factory=dict, max_length=10)
    decisions: list[ApplicabilityDecision] = Field(default_factory=list, max_length=72)
    purposes: dict[str, Purpose] = Field(default_factory=dict, max_length=100)

    @field_validator('purposes')
    @classmethod
    def valid_uids(cls, value):
        if any(not key or len(key) > 64 for key in value):
            raise ValueError('文件标识不合法')
        return value

    @model_validator(mode='after')
    def valid_scope(self):
        if self.scope == 'system' and not self.scope_description:
            raise ValueError('体系文件集检查必须填写组织范围')
        clauses = [item.clause for item in self.decisions]
        if len(set(clauses)) != len(clauses):
            raise ValueError('不适用依据中条款不可重复')
        return self


def freeze_context(context: PrescreenContext | None, *, user_id: int, file_uids: list[str]) -> dict:
    """调用者已校验文件权限；拒绝旁系UID，冻结本次事实及授权人员声明。"""
    value = (context or PrescreenContext()).model_dump(mode='json')
    if set(value['purposes']) - set(file_uids):
        raise ValueError('文件用途包含不在本次范围内的文件')
    from App.Services.Rules.RequirementCatalog import load_catalog
    clauses = {item['clause'] for item in load_catalog()['requirements']}
    if any(item['clause'] not in clauses for item in value['decisions']):
        raise ValueError('不适用依据包含未定义的条款')
    value['as_of_date'] = value['as_of_date'] or now().date().isoformat()
    timestamp = now().isoformat()
    for decision in value['decisions']:
        decision.update(confirmed_by=user_id, confirmed_at=timestamp)
    return value


def context_dict(context=None) -> dict:
    """引擎内部只读使用；已冻结的字典不再进入客户端输入模型。"""
    if isinstance(context, PrescreenContext):
        return context.model_dump(mode='json')
    return context if context is not None else PrescreenContext().model_dump(mode='json')
