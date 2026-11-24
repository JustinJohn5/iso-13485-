"""复用实际规则与文件关联检查，产出整套检查快照。"""
from datetime import date
from types import SimpleNamespace

from App.Services.DocumentControl.ReviewEngine import build_review, review_ready
from App.Services.ManualSuites.Catalog import catalog
from App.Services.Rules.RuleEngine import DocumentInput, RuleEngine
from App.Schemas.Prescreen import context_dict
from App.Services.Rules.PrescreenReport import build_prescreen_report, evaluation_dict
from App.Services.ScoringService import build_score
from App.Utils.Errors import ApiError
from App.Utils.TimeUtils import now


def inspect_items(items: list[dict], rules, as_of: str, context=None) -> dict:
    if not items:
        raise ApiError(1001, '请先生成或导入文件')
    inputs = [DocumentInput(file_id=i, file_uid=row['id'], name=row['title'],
                            document_type=row['document_type'], text='' if row.get('text_status') == 'insufficient' else row['text'], char_count=len(row['text']),
                            template_id=row.get('snapshot', {}).get('template_id', '') or row.get('catalog_key', ''),
                            text_status=row.get('text_status', 'ok'))
              for i, row in enumerate(items, 1)]
    files = [SimpleNamespace(file_uid=row['id'], original_name=row['title'], document_type=row['document_type'],
                             extracted_text=row['text'], sha256=row['sha256']) for row in items]
    frozen = {**context_dict(context), 'as_of_date': as_of}
    overrides = {row['id']: {'revision': row['file_version'], 'number': row['number'],
                             **({'layer': 'record'} if frozen['purposes'].get(row['id']) == 'record' else {})} for row in items}
    review = build_review(files, date.fromisoformat(as_of), overrides)
    findings = RuleEngine(rules).evaluate(inputs, frozen, review=review)
    score = build_score(rules, findings, document_conflicts=not review_ready(review)).to_dict()
    present = {row['catalog_key'] for row in items}
    return dict(checked_at=now().isoformat(), rule_set=dict(rule_set_id=rules.rule_set_id, title=rules.title,
                version=rules.version, standard=rules.standard), score=score, review=review,
                missing_catalog=[row for row in catalog() if row['key'] not in present],
                prescreen=build_prescreen_report(rules, findings, frozen, review=review),
                findings=[evaluation_dict(row) for row in findings],
                summary='存在冲突，待核对' if not review_ready(review) else '文本检查完成，待人工复核',
                disclaimer='本结果仅为文本规则预筛，生成件为待复核草稿，不构成认证、正式审核结论或法规符合性声明。')
