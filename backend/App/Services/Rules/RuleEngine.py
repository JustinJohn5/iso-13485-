"""规则引擎：把抽取后的文档文本与规则包比对，产出逐条判定结果。"""

from __future__ import annotations

from dataclasses import dataclass, field

from App.Services.Rules.RuleModels import CheckSpec, Rule, RuleSet
from App.Services.Rules.Checks import (
    check_absent,
    check_all_terms,
    check_date,
    check_length,
    check_present,
    check_section,
    find_missing_documents,
)
from App.Utils.Logger import get_logger

logger = get_logger(__name__)

STATUS_PASS = "pass"
STATUS_FAIL = "fail"
STATUS_SKIPPED = "skipped"


@dataclass(frozen=True)
class DocumentInput:
    """参与判定的文档（已抽取出纯文本）。"""

    file_id: int
    file_uid: str
    name: str
    document_type: str
    text: str
    page_count: int = 0
    char_count: int = 0


@dataclass
class RuleEvaluation:
    """一条规则的一次判定结果。"""

    rule: Rule
    status: str
    evidence: str = ""
    detail: str = ""
    document_name: str = ""
    document_type: str = ""
    document_uid: str = ""
    order: int = 0

    @property
    def passed(self) -> bool:
        return self.status == STATUS_PASS


def _run_check(spec: CheckSpec, text: str) -> tuple[bool, str, str]:
    """根据校验类型分派到具体判定函数。"""
    if spec.type == "present":
        outcome = check_present(text, spec)
    elif spec.type == "absent":
        outcome = check_absent(text, spec)
    elif spec.type == "section":
        outcome = check_section(text, spec)
    elif spec.type == "all_terms":
        outcome = check_all_terms(text, spec)
    elif spec.type == "date":
        outcome = check_date(text, spec)
    elif spec.type == "length":
        outcome = check_length(text, spec)
    else:
        return False, "", f"暂不支持的校验类型：{spec.type}"
    return outcome.passed, outcome.evidence, outcome.detail


class RuleEngine:
    """无状态规则执行器。"""

    def __init__(self, rule_set: RuleSet) -> None:
        self._rule_set = rule_set

    def evaluate(self, documents: list[DocumentInput]) -> list[RuleEvaluation]:
        """执行全部适用规则，返回逐条结果（含跳过项）。"""
        by_type: dict[str, list[DocumentInput]] = {}
        for document in documents:
            by_type.setdefault(document.document_type, []).append(document)

        present_types = set(by_type.keys())
        evaluations: list[RuleEvaluation] = []
        order = 0

        for rule in self._rule_set.rules:
            order += 1
            if rule.check.type == "required_documents":
                evaluations.append(self._evaluate_coverage(rule, present_types, order))
                continue

            targets = (
                documents
                if "*" in rule.document_types
                else [doc for doc in documents if doc.document_type in rule.document_types]
            )
            if not targets:
                evaluations.append(
                    RuleEvaluation(
                        rule=rule,
                        status=STATUS_SKIPPED,
                        detail="未上传适用文档，本规则未参与判定",
                        order=order,
                    )
                )
                continue

            if rule.per_document:
                for document in targets:
                    passed, evidence, detail = _run_check(rule.check, document.text)
                    evaluations.append(
                        RuleEvaluation(
                            rule=rule,
                            status=STATUS_PASS if passed else STATUS_FAIL,
                            evidence=evidence,
                            detail=detail,
                            document_name=document.name,
                            document_type=document.document_type,
                            document_uid=document.file_uid,
                            order=order,
                        )
                    )
            else:
                merged = "\n".join(doc.text for doc in targets)
                passed, evidence, detail = _run_check(rule.check, merged)
                evaluations.append(
                    RuleEvaluation(
                        rule=rule,
                        status=STATUS_PASS if passed else STATUS_FAIL,
                        evidence=evidence,
                        detail=detail,
                        document_name="、".join(doc.name for doc in targets)[:300],
                        document_type=targets[0].document_type,
                        order=order,
                    )
                )
        return evaluations

    def _evaluate_coverage(
        self, rule: Rule, present_types: set[str], order: int
    ) -> RuleEvaluation:
        """体系完整性：检查必需文档类型是否齐全。"""
        missing = find_missing_documents(present_types, rule.check)
        if not missing:
            return RuleEvaluation(
                rule=rule,
                status=STATUS_PASS,
                evidence="必需文档类型均已上传",
                detail="体系文件完整",
                document_name="体系文件集",
                order=order,
            )
        labels = [self._rule_set.document_type_label(item) for item in missing]
        return RuleEvaluation(
            rule=rule,
            status=STATUS_FAIL,
            evidence=f"缺少文档类型：{'、'.join(labels)}",
            detail=f"缺少 {len(missing)} 类必需文档",
            document_name="体系文件集",
            order=order,
        )
