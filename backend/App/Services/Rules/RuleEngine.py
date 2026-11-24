"""规则引擎：把抽取后的文档文本与规则包比对，产出逐条判定结果。"""

from __future__ import annotations

from dataclasses import dataclass, field

from App.Schemas.Prescreen import context_dict
from App.Services.Rules.Applicability import applicable_targets, condition_state
from App.Services.Rules.ControlledReferences import ControlledReferences
from App.Services.Rules.EvidenceChecks import (
    apply_boundaries, check_control, check_requirement, prepare_documents, uniform_checks,
)

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
    purpose: str = 'auto'
    template_id: str = ''
    text_status: str = 'ok'


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
    assessment_status: str = ''
    basis_kind: str = 'standard'
    source: dict | str = field(default_factory=dict)
    matched_terms: list[str] = field(default_factory=list)
    missing_terms: list[str] = field(default_factory=list)
    locations: list[dict] = field(default_factory=list)
    manual_review: list[str] = field(default_factory=list)
    checks: list[dict] = field(default_factory=list)
    applicability_unknown: bool = False
    purpose: str = 'auto'

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

    def evaluate(self, documents: list[DocumentInput], context=None, *, review=None) -> list[RuleEvaluation]:
        """执行全部适用规则，返回逐条结果（含跳过项）。"""
        if self._rule_set.version == '2.0.0' and self._rule_set.rule_set_id == 'iso13485-core':
            return self._evaluate_prescreen(documents, context_dict(context), review or {})
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

    def _evaluate_prescreen(self, documents, context, review):
        evaluations = []
        prepared = prepare_documents(documents)
        references = ControlledReferences(documents, review)
        for order, rule in enumerate(self._rule_set.rules, 1):
            targets = applicable_targets(rule, documents, lambda doc: self._purpose(doc, context))
            state, reason = condition_state(rule, context)
            if not targets and context.get('scope') != 'system':
                state, reason = 'out_of_scope', '本次文件不承载此要求；不代表组织不适用'
            elif not targets and not state:
                state, reason = 'gap', '体系范围内本次未提供承载文件，请补充依据；不表示组织没有该文件'
            if state:
                checks = uniform_checks(rule, state, reason)
                if state == 'gap':
                    checks = apply_boundaries(rule, checks, context)
                evaluations.append(self._prescreen_row(rule, order, state, reason, targets,
                    checks=checks, manual_review=[rule.uncertainty] if state == 'gap' and rule.uncertainty else [],
                    applicability_unknown=bool(rule.conditions and state == 'pending_input')))
                continue
            if rule.check.type == 'requirement':
                record_targets = [doc for doc in targets if self._purpose(doc, context) in ('report', 'record', 'form')]
                for document in record_targets:
                    outcome = check_requirement(document, rule, self._purpose(document, context),
                                                context, prepared, references)
                    evaluations.append(self._outcome_row(rule, order, document, outcome, context))
                targets = [doc for doc in targets if doc not in record_targets]
                if not targets:
                    continue
                outcomes = [(document, check_requirement(document, rule, self._purpose(document, context),
                                                         context, prepared, references))
                            for document in targets]
                # 同一要求由一个或多个文件承载；选用最完整的单份证据，跨文件拼接交人工取证。
                document, outcome = min(outcomes, key=lambda row: (
                    row[1].assessment_status != 'evidence_found', len(row[1].missing_terms)))
                if len(outcomes) > 1 and outcome.assessment_status != 'evidence_found':
                    outcome.manual_review.append('存在多个候选承载文件；跨文件引用、对象和版本的证据链须人工核对。')
                evaluations.append(self._outcome_row(rule, order, document, outcome, context))
            else:
                for document in targets:
                    outcome = check_control(document, rule, context)
                    evaluations.append(self._outcome_row(rule, order, document, outcome, context))
        return evaluations

    @staticmethod
    def _purpose(document, context):
        explicit = context.get('purposes', {}).get(document.file_uid, document.purpose)
        if explicit != 'auto':
            return explicit
        name = document.name
        for marker, purpose in [('报告', 'report'), ('记录', 'record'), ('表单', 'form'),
                                ('计划', 'plan'), ('规程', 'instruction'), ('程序', 'procedure')]:
            if marker in name:
                return purpose
        return 'auto'

    @staticmethod
    def _prescreen_row(rule, order, state, detail, targets, **values):
        legacy = 'pass' if state == 'evidence_found' else ('skipped' if state in (
            'manual_review', 'not_applicable', 'out_of_scope') else 'fail')
        return RuleEvaluation(rule=rule, status=legacy, assessment_status=state, detail=detail,
            order=order, source=rule.source, basis_kind=rule.basis_kind,
            document_name='、'.join(row.name for row in targets)[:300],
            document_type=targets[0].document_type if targets else '',
            document_uid=targets[0].file_uid if len(targets) == 1 else '', **values)

    def _outcome_row(self, rule, order, document, outcome, context):
        if document.text_status == 'partial':
            note = '部分内容无法抽取，请在原件中核对图像、扫描页或截断区域。'
            outcome.manual_review.append(note)
            if outcome.assessment_status == 'gap':
                outcome.assessment_status, outcome.detail = 'unreadable', note
            for check in outcome.checks:
                if check['assessment_status'] == 'gap':
                    check.update(assessment_status='unreadable', detail=note)
        row = self._prescreen_row(rule, order, outcome.assessment_status, outcome.detail, [document],
                                  purpose=self._purpose(document, context))
        for key in ('evidence', 'matched_terms', 'missing_terms', 'locations', 'manual_review', 'checks'):
            setattr(row, key, getattr(outcome, key))
        return row

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
