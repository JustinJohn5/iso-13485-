"""规则包数据模型。

规则包为纯 JSON 数据，新增条款只改数据、不改代码。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Severity = Literal["critical", "major", "minor", "observation"]
CheckType = Literal[
    "present",
    "absent",
    "section",
    "all_terms",
    "date",
    "length",
    "required_documents",
    "requirement",
]


class CheckSpec(BaseModel):
    """单条规则的判定方式。"""

    type: CheckType
    # present / absent / date 使用的正则表达式（不区分大小写）
    patterns: list[str] = Field(default_factory=list)
    # present 需要命中的最少次数
    min_matches: int = 1
    # section 使用的标题同义词（任一命中即视为存在该章节）
    headings: list[str] = Field(default_factory=list)
    # all_terms 使用的词组集合，每个子列表内的词互为同义词；默认需全部命中
    terms: list[list[str]] = Field(default_factory=list)
    # all_terms 允许命中的最少词组数；为空表示要求全部命中
    min_groups: int | None = None
    # length 使用的最小字符数
    min_chars: int = 0
    # date 使用的有效期限：距今最大天数 / 是否禁止未来日期
    max_age_days: int | None = None
    not_future: bool = True
    # required_documents 需要的文档类型
    documents: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_consistency(self) -> "CheckSpec":
        if self.type in ("present", "absent") and not self.patterns:
            raise ValueError("present/absent 校验必须提供 patterns")
        if self.type == "section" and not self.headings:
            raise ValueError("section 校验必须提供 headings")
        if self.type in ("all_terms", "requirement") and not self.terms:
            raise ValueError("all_terms 校验必须提供 terms")
        if self.type == "date" and not self.patterns:
            raise ValueError("date 校验必须提供 patterns")
        if self.type == "length" and self.min_chars <= 0:
            raise ValueError("length 校验必须提供大于 0 的 min_chars")
        if self.type == "required_documents" and not self.documents:
            raise ValueError("required_documents 校验必须提供 documents")
        if self.min_groups is not None and self.min_groups < 1:
            raise ValueError("min_groups 必须大于等于 1")
        return self


class Rule(BaseModel):
    """一条 ISO 13485 合规判定规则。"""

    rule_id: str
    title: str
    clause: str
    clause_title: str
    severity: Severity
    document_types: list[str] = Field(default_factory=lambda: ["*"])
    check: CheckSpec
    rationale: str = ""
    suggestion: str = ""
    # 是否逐份文档判定；False 时对同类文档的合并文本判定一次
    per_document: bool = True
    basis_kind: str = 'standard'
    source: dict | str = Field(default_factory=dict)
    templates: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    uncertainty: str = ''
    evidence_requirements: list[str] = Field(default_factory=list)

    @field_validator("rule_id")
    @classmethod
    def _check_rule_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("rule_id 不能为空")
        return cleaned


class DocumentTypeDef(BaseModel):
    """质量体系文档类型定义。"""

    type: str
    label: str
    clauses: list[str] = Field(default_factory=list)
    required: bool = False
    keywords: list[str] = Field(default_factory=list)
    description: str = ""


class SeverityDef(BaseModel):
    """严重程度定义：展示名、权重、得分上限。"""

    label: str
    weight: float
    score_cap: float | None = None


class RuleSet(BaseModel):
    """一个完整规则包。"""

    rule_set_id: str
    version: str
    title: str
    standard: str = "ISO 13485:2016"
    description: str = ""
    document_types: list[DocumentTypeDef] = Field(default_factory=list)
    severities: dict[str, SeverityDef] = Field(default_factory=dict)
    rules: list[Rule] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_unique(self) -> "RuleSet":
        ids = [rule.rule_id for rule in self.rules]
        duplicated = {rid for rid in ids if ids.count(rid) > 1}
        if duplicated:
            raise ValueError(f"规则编号重复：{sorted(duplicated)}")
        if not self.rules:
            raise ValueError("规则包分片至少需要一条规则")
        return self

    def document_type_label(self, doc_type: str) -> str:
        """按类型标识取中文名称。"""
        for item in self.document_types:
            if item.type == doc_type:
                return item.label
        return doc_type

    def validate_references(self) -> None:
        """合并分片后校验：规则引用的文档类型必须已定义。"""
        known_types = {item.type for item in self.document_types}
        for rule in self.rules:
            for doc_type in rule.document_types:
                if doc_type != "*" and doc_type not in known_types:
                    raise ValueError(f"规则 {rule.rule_id} 引用了未定义的文档类型：{doc_type}")
            if rule.check.type == "required_documents":
                for doc_type in rule.check.documents:
                    if doc_type not in known_types:
                        raise ValueError(f"规则 {rule.rule_id} 引用了未定义的文档类型：{doc_type}")
