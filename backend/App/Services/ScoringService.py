"""评分与结论：把逐条判定换算成合规得分、结论与条款覆盖矩阵。"""

from __future__ import annotations

from dataclasses import dataclass, field

from App.Services.Rules.RuleEngine import STATUS_FAIL, STATUS_PASS, STATUS_SKIPPED, RuleEvaluation
from App.Services.Rules.RuleModels import RuleSet, SeverityDef
from App.Services.Rules.PrescreenReport import coverage_for

DEFAULT_SEVERITY_WEIGHTS: dict[str, float] = {
    "critical": 10.0,
    "major": 5.0,
    "minor": 2.0,
    "observation": 1.0,
}
DEFAULT_SCORE_CAPS: dict[str, float] = {"critical": 45.0, "major": 75.0}

VERDICT_PASS = "符合"
VERDICT_BASIC = "基本符合"
VERDICT_RECTIFY = "需整改"
VERDICT_FAIL = "不符合"


@dataclass
class ClauseCoverage:
    """按条款聚合的通过情况。"""

    clause: str
    clause_title: str
    passed: int = 0
    failed: int = 0

    @property
    def total(self) -> int:
        return self.passed + self.failed

    @property
    def status(self) -> str:
        if self.failed == 0:
            return "pass"
        if self.passed == 0:
            return "fail"
        return "partial"

    def to_dict(self) -> dict:
        return {
            "clause": self.clause,
            "clause_title": self.clause_title,
            "passed": self.passed,
            "failed": self.failed,
            "total": self.total,
            "status": self.status,
            "rate": round(self.passed / self.total * 100, 1) if self.total else 0.0,
        }


@dataclass
class ScoreResult:
    """一次校验的评分结果。"""

    score: float
    verdict: str
    passed_count: int
    failed_count: int
    skipped_count: int
    total_count: int
    critical_count: int
    major_count: int
    minor_count: int
    observation_count: int
    clause_matrix: list[ClauseCoverage] = field(default_factory=list)
    coverage: dict | None = None

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "verdict": self.verdict,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "skipped_count": self.skipped_count,
            "total_count": self.total_count,
            "critical_count": self.critical_count,
            "major_count": self.major_count,
            "minor_count": self.minor_count,
            "observation_count": self.observation_count,
            "clause_matrix": [item.to_dict() for item in self.clause_matrix],
            "coverage": self.coverage,
        }


def _severity_def(rule_set: RuleSet, severity: str) -> SeverityDef:
    defined = rule_set.severities.get(severity)
    if defined is not None:
        return defined
    return SeverityDef(
        label=severity,
        weight=DEFAULT_SEVERITY_WEIGHTS.get(severity, 1.0),
        score_cap=DEFAULT_SCORE_CAPS.get(severity),
    )


def build_score(rule_set: RuleSet, evaluations: list[RuleEvaluation], *, document_conflicts: bool = False) -> ScoreResult:
    """按严重程度加权计算得分，并对严重不符合设置得分上限。"""
    if rule_set.rule_set_id == 'iso13485-core' and rule_set.version == '2.0.0':
        coverage = coverage_for(evaluations)
        counts = {key: sum(row.assessment_status == key for row in evaluations)
                  for key in ('evidence_found', 'gap', 'pending_input', 'conflict', 'unreadable')}
        if document_conflicts or counts['conflict']:
            verdict = '存在冲突，待核对'
        elif counts['unreadable']:
            verdict = '部分资料无法判定'
        elif counts['pending_input']:
            verdict = '存在待补信息'
        elif counts['gap']:
            verdict = '存在文本缺口'
        elif not coverage['computable']:
            verdict = '不具备计算条件'
        else:
            verdict = '已检出文本线索，待实施取证'
        failed = sum(row.status == STATUS_FAIL for row in evaluations)
        passed = counts['evidence_found']
        return ScoreResult(score=coverage['value'] or 0.0, verdict=verdict, passed_count=passed,
                           failed_count=failed, skipped_count=len(evaluations)-passed-failed,
                           total_count=passed+failed, critical_count=0, major_count=0,
                           minor_count=0, observation_count=0,
                           clause_matrix=_build_clause_matrix(evaluations), coverage=coverage)
    applicable = [item for item in evaluations if item.status != STATUS_SKIPPED]
    passed = [item for item in applicable if item.status == STATUS_PASS]
    failed = [item for item in applicable if item.status == STATUS_FAIL]
    skipped = [item for item in evaluations if item.status == STATUS_SKIPPED]

    total_weight = 0.0
    passed_weight = 0.0
    counts = {"critical": 0, "major": 0, "minor": 0, "observation": 0}

    for item in applicable:
        severity = _severity_def(rule_set, item.rule.severity)
        weight = max(severity.weight, 0.1)
        total_weight += weight
        if item.status == STATUS_PASS:
            passed_weight += weight

    raw_score = 100.0 if total_weight == 0 else passed_weight / total_weight * 100.0

    caps: list[float] = []
    for item in failed:
        severity = _severity_def(rule_set, item.rule.severity)
        counts[item.rule.severity] = counts.get(item.rule.severity, 0) + 1
        if severity.score_cap is not None:
            caps.append(float(severity.score_cap))

    score = min([raw_score, *caps]) if caps else raw_score
    score = round(max(0.0, min(100.0, score)), 1)

    verdict = _decide_verdict(score, counts["critical"], counts["major"])
    if document_conflicts and verdict in {VERDICT_PASS, VERDICT_BASIC}:
        verdict = '存在冲突，待修订'

    return ScoreResult(
        score=score,
        verdict=verdict,
        passed_count=len(passed),
        failed_count=len(failed),
        skipped_count=len(skipped),
        total_count=len(applicable),
        critical_count=counts["critical"],
        major_count=counts["major"],
        minor_count=counts["minor"],
        observation_count=counts["observation"],
        clause_matrix=_build_clause_matrix(applicable),
    )


def _decide_verdict(score: float, critical: int, major: int) -> str:
    """结论判定：严重不符合优先，其次看得分与主要不符合数量。"""
    if critical > 0:
        return VERDICT_FAIL
    if score >= 90 and major == 0:
        return VERDICT_PASS
    if score >= 75:
        return VERDICT_BASIC
    if score >= 60:
        return VERDICT_RECTIFY
    return VERDICT_FAIL


def _build_clause_matrix(evaluations: list[RuleEvaluation]) -> list[ClauseCoverage]:
    """按条款聚合通过/未通过数量，保持条款自然顺序。"""
    matrix: dict[str, ClauseCoverage] = {}
    for item in evaluations:
        if item.status == STATUS_SKIPPED:
            continue
        key = item.rule.clause
        coverage = matrix.get(key)
        if coverage is None:
            coverage = ClauseCoverage(clause=key, clause_title=item.rule.clause_title)
            matrix[key] = coverage
        if item.status == STATUS_PASS:
            coverage.passed += 1
        else:
            coverage.failed += 1
    return sorted(matrix.values(), key=lambda item: _clause_sort_key(item.clause))


def _clause_sort_key(clause: str) -> tuple:
    parts = []
    for part in clause.split("."):
        parts.append((0, int(part)) if part.isdigit() else (1, part))
    return tuple(parts)
