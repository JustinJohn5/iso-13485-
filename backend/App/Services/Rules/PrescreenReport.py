"""冻结可追溯结果与不加权覆盖率；不把未知适用性或人工问题并入通过。"""
from collections import Counter

from App.Schemas.Prescreen import context_dict

STATUSES = ('evidence_found', 'gap', 'pending_input', 'conflict', 'unreadable', 'manual_review',
            'not_applicable', 'out_of_scope')


def evaluation_dict(row):
    return dict(rule_id=row.rule.rule_id, title=row.rule.title, clause=row.rule.clause,
                clause_title=row.rule.clause_title, severity=row.rule.severity, status=row.status,
                assessment_status=row.assessment_status, detail=row.detail, evidence=row.evidence,
                document_uid=row.document_uid, document_name=row.document_name, document_type=row.document_type,
                purpose=row.purpose, source=row.source, basis_kind=row.basis_kind,
                matched_terms=row.matched_terms, missing_terms=row.missing_terms, locations=row.locations,
                manual_review=row.manual_review, checks=row.checks, applicability_unknown=row.applicability_unknown,
                conditions=row.rule.conditions, suggestion=row.rule.suggestion)


def coverage_for(evaluations):
    numerator = denominator = 0
    for row in evaluations:
        if row.applicability_unknown:
            continue
        units = row.checks or [{'assessment_status': row.assessment_status}]
        for check in units:
            if check.get('applicability_unknown') or check['assessment_status'] in ('manual_review', 'not_applicable', 'out_of_scope'):
                continue
            denominator += 1
            numerator += check['assessment_status'] == 'evidence_found'
    return dict(value=round(numerator / denominator * 100, 1) if denominator else None,
                computable=bool(denominator), denominator=denominator, numerator=numerator)


def build_prescreen_report(rules, evaluations, context=None, *, review=None):
    if rules.rule_set_id != 'iso13485-core' or rules.version != '2.0.0':
        return None
    frozen = context_dict(context)
    counts = Counter(row.assessment_status for row in evaluations)
    review = review or {}
    counts['conflict'] += len(review.get('version_groups', [])) + len(review.get('requirement_conflicts', []))
    manual = []
    for row in evaluations:
        questions = row.manual_review or ([row.detail] if row.assessment_status == 'manual_review' else [])
        for question in questions:
            manual.append(dict(rule_id=row.rule.rule_id, clause=row.rule.clause,
                               document_uid=row.document_uid, question=question))
    return dict(version=rules.version, scope=frozen.get('scope', 'documents'),
                scope_description=frozen.get('scope_description', ''), as_of_date=frozen.get('as_of_date'),
                coverage=coverage_for(evaluations), counts={key: counts.get(key, 0) for key in STATUSES},
                applicability_pending=sum(row.applicability_unknown or any(
                    check.get('applicability_unknown') for check in row.checks) for row in evaluations),
                items=[evaluation_dict(row) for row in evaluations], manual_questions=manual, context=frozen,
                calculation='按子检查和对象不加权；未知适用性、仅人工事项、不适用及本文件不承载项单列；零分母不计算。',
                boundary='结果仅为所提供范围的基础文本线索；实施、真实批准、法规适用与符合性需人工审核。')
