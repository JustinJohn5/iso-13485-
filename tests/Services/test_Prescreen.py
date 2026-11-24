"""新规则的证据、适用性、范围与覆盖率回归。"""
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from App.Schemas.Prescreen import PrescreenContext, freeze_context
from App.Services.Rules.PrescreenReport import build_prescreen_report
from App.Services.Rules.RuleEngine import DocumentInput, RuleEngine
from App.Services.Rules.RuleModels import CheckSpec, Rule, RuleSet
from App.Services.Rules.RuleSetLoader import RuleSetLoader
from App.Services.ScoringService import build_score


def rules(conditions=None, uncertainty=''):
    return RuleSet(rule_set_id='iso13485-core', version='2.0.0', title='预筛', rules=[
        Rule(rule_id='R-7.3.2', title='设计策划', clause='7.3.2', clause_title='设计策划',
             severity='observation', document_types=['design_control'], topics=['设计'],
             conditions=conditions or [], uncertainty=uncertainty, basis_kind='standard',
             check=CheckSpec(type='requirement', terms=[['职责', '责任'], ['阶段', '里程碑']]))])


def doc(text, **values):
    return DocumentInput(1, 'd1', values.pop('name', '设计计划.txt'),
                         values.pop('document_type', 'design_control'), text, **values)


def evaluate(text, context=None, **values):
    return RuleEngine(rules()).evaluate([doc(text, **values)], context)[0]


def test_headings_and_placeholders_do_not_become_completed_evidence():
    assert evaluate('职责\n阶段').assessment_status == 'gap'
    result = evaluate('职责：待确认\n阶段：待填写')
    assert result.assessment_status == 'pending_input'
    assert result.missing_terms == ['职责', '阶段']


def test_synonyms_have_unmodified_quote_and_real_text_line_location():
    result = evaluate('责任由研发主管承担；项目里程碑由项目经理组织评审。')
    assert result.assessment_status == 'evidence_found'
    assert result.matched_terms == ['责任', '里程碑']
    assert result.locations[0]['line'] == 1
    assert '研发主管' in result.locations[0]['quote']
    assert result.locations[0]['kind'] == 'extracted_line'
    assert result.manual_review


def test_negative_evidence_and_different_objects_are_not_combined():
    assert evaluate('未规定职责，也未确定阶段。').assessment_status != 'evidence_found'
    result = evaluate('产品A的职责由研发负责。\n产品B的阶段由项目经理确定。')
    assert result.assessment_status == 'manual_review'


def test_unreadable_text_is_not_reported_as_missing():
    assert evaluate('').assessment_status == 'unreadable'


def test_generic_procedure_does_not_route_by_incidental_body_word():
    value = evaluate('采购部只负责通知设计部门。', name='通知程序.txt', document_type='procedure')
    assert value.assessment_status == 'out_of_scope'


def test_file_scope_does_not_demand_other_types_but_system_scope_does():
    unrelated = doc('采购部负责执行采购程序。', name='采购程序.txt', document_type='purchasing')
    engine = RuleEngine(rules())
    assert engine.evaluate([unrelated])[0].assessment_status == 'out_of_scope'
    context = PrescreenContext(scope='system', scope_description='组织全部设计开发活动', facts={'design': 'yes'})
    assert engine.evaluate([unrelated], context)[0].assessment_status == 'gap'


def test_unknown_condition_and_unsupported_exclusion_stay_visible():
    engine = RuleEngine(rules(['design']))
    item = doc('责任由研发主管承担；项目阶段由项目经理组织评审。')
    assert engine.evaluate([item])[0].assessment_status == 'pending_input'
    context = PrescreenContext(facts={'design': 'no'})
    assert engine.evaluate([item], context)[0].assessment_status == 'pending_input'
    context = PrescreenContext(facts={'design': 'no'}, decisions=[
        {'clause': '7.3.2', 'reason': '本公司没有研发部门', 'basis': '由供应商承担研发活动'}])
    assert engine.evaluate([item], context)[0].assessment_status == 'manual_review'


def test_confirmed_non_applicability_has_server_actor_and_basis():
    engine = RuleEngine(rules(['sterile']))
    context = PrescreenContext(facts={'sterile': 'no'}, decisions=[
        {'clause': '7.3.2', 'reason': '产品为非无菌产品', 'basis': '已批准的注册产品技术要求'}])
    frozen = freeze_context(context, user_id=9, file_uids=['d1'])
    result = engine.evaluate([doc('责任由研发主管承担。')], frozen)[0]
    assert result.assessment_status == 'not_applicable'
    assert frozen['decisions'][0]['confirmed_by'] == 9
    assert frozen['decisions'][0]['confirmed_at']


def test_context_rejects_forged_actor_unknown_fact_and_invalid_scope():
    with pytest.raises(ValidationError):
        PrescreenContext(decisions=[{'clause': '7.3.2', 'reason': '事实说明', 'basis': '依据说明', 'confirmed_by': 1}])
    with pytest.raises(ValidationError):
        PrescreenContext(facts={'secret': 'no'})
    with pytest.raises(ValidationError):
        PrescreenContext(scope='system')
    with pytest.raises(ValueError):
        freeze_context(PrescreenContext(purposes={'other': 'record'}), user_id=9, file_uids=['d1'])


def test_zero_denominator_is_not_full_coverage_and_no_conformity_verdict():
    values = RuleEngine(rules()).evaluate([doc('采购职责由采购部承担。', document_type='purchasing')])
    report = build_prescreen_report(rules(), values, PrescreenContext())
    assert report['coverage'] == {'value': None, 'computable': False, 'denominator': 0, 'numerator': 0}
    result = build_score(rules(), values)
    assert result.score == 0
    assert result.verdict not in ('符合', '基本符合', '不符合')


def test_individual_required_groups_do_not_offset_missing_groups():
    value = evaluate('责任由研发主管承担。')
    assert value.assessment_status == 'gap'
    assert len(value.checks) == 2
    report = build_prescreen_report(rules(), [value], PrescreenContext())
    assert report['coverage']['denominator'] == 2
    assert report['coverage']['numerator'] == 1


def test_source_uncertainty_stays_manual_even_with_terms():
    result = RuleEngine(rules(uncertainty='用户译文需核对')).evaluate([
        doc('责任由研发主管承担；项目阶段由项目经理组织评审。')])[0]
    assert result.assessment_status == 'manual_review'


@pytest.mark.parametrize('text,expected', [
    ('批准：____', 'pending_input'), ('批准：待填写', 'pending_input'),
    ('批准：张三 2026-11-01', 'evidence_found'),
    ('生效日期：2026-02-30', 'pending_input'),
    ('生效日期：2027-01-01', 'manual_review')])
def test_control_fields_do_not_imply_authentic_approval_or_invalid_dates(text, expected):
    bundle = RuleSetLoader(Path(__file__).resolve().parents[2] / 'backend/App/Rules').get()
    code = 'DOC-003' if text.startswith('批准') else 'DOC-004'
    result = next(row for row in RuleEngine(bundle).evaluate([
        doc(text)], PrescreenContext(as_of_date=date(2026, 11, 24))) if row.rule.rule_id == code)
    assert result.assessment_status == expected


def test_outsourced_design_is_still_applicable():
    context = PrescreenContext(facts={'design': 'yes', 'outsourcing': 'yes'})
    result = RuleEngine(rules(['design'])).evaluate([doc('责任：待确认\n阶段：待填写')], context)[0]
    assert result.assessment_status == 'pending_input'


def test_unprovided_controlled_reference_requires_evidence():
    value = evaluate('设计职责和阶段按照 QP-03 V2.0 执行，参见该程序。')
    assert value.assessment_status == 'pending_input'


def test_generic_reference_and_keyword_list_are_not_substantive_arrangements():
    assert evaluate('职责和阶段参照有关文件。').assessment_status == 'pending_input'
    assert evaluate('本程序应规定以下内容：职责、阶段。').assessment_status != 'evidence_found'


def test_distinct_record_objects_are_checked_separately():
    values = RuleEngine(rules()).evaluate([
        doc('责任由研发主管承担；阶段由项目负责人安排。', name='设计记录甲.txt'),
        DocumentInput(2, 'd2', '设计记录乙.txt', 'design_control', '职责：待确认\n阶段：待填写')])
    assert len(values) == 2
    assert {row.document_uid for row in values} == {'d1', 'd2'}


def test_pending_same_element_is_not_hidden_by_another_positive_line():
    value = evaluate('职责由研发负责人承担。\n另一事项职责：待确认\n阶段由项目经理安排。')
    assert value.assessment_status == 'pending_input'


def test_plan_only_routes_to_design_planning_and_general_requirements():
    bundle = RuleSetLoader(Path(__file__).resolve().parents[2] / 'backend/App/Rules').get()
    rows = RuleEngine(bundle).evaluate([doc('项目阶段由设计负责人确定。')], PrescreenContext(facts={'design': 'yes'}))
    assert {row.rule.clause for row in rows if row.rule.clause.startswith('7.3.')
            and row.assessment_status != 'out_of_scope'} == {'7.3.1', '7.3.2'}


def test_unreadable_and_missing_carrier_keep_all_defined_check_units():
    engine = RuleEngine(rules())
    context = PrescreenContext(scope='system', scope_description='包括设计活动')
    for items in ([doc('')], []):
        report = build_prescreen_report(rules(), engine.evaluate(items, context), context)
        assert report['coverage']['denominator'] == 2


def test_actual_record_requires_filled_observations():
    value = evaluate('项目责任由研发主管承担；阶段由项目负责人安排。\n计划日期：2027-05-01\n结果：待填写\n执行人：____', purpose='record')
    assert value.assessment_status == 'pending_input'


def test_negated_approval_is_not_a_filled_approval_value():
    bundle = RuleSetLoader(Path(__file__).resolve().parents[2] / 'backend/App/Rules').get()
    rows = RuleEngine(bundle).evaluate([doc('尚未批准，等待评审通过。')])
    assert next(row for row in rows if row.rule.rule_id == 'DOC-003').assessment_status == 'pending_input'


def test_design_regulatory_substantiation_stays_for_manual_verification():
    context = PrescreenContext(facts={'design': 'no', 'outsourcing': 'yes'}, decisions=[
        {'clause': '7.3.2', 'reason': '本公司将全部设计外包', 'basis': '未有法规允许删除设计'}])
    frozen = freeze_context(context, user_id=9, file_uids=['d1'])
    assert RuleEngine(rules(['design'])).evaluate([doc('设计计划由研发主管负责。')], frozen)[0].assessment_status == 'manual_review'


def test_future_control_verb_does_not_cancel_express_denial():
    result = evaluate('未开展职责确认，但应当由研发负责人安排。\n阶段由项目经理安排。')
    assert result.checks[0]['assessment_status'] == 'gap'


def test_composite_process_and_software_conditions_are_separate():
    bundle = RuleSetLoader(Path(__file__).resolve().parents[2] / 'backend/App/Rules').get()
    context = PrescreenContext(scope='system', scope_description='生产和服务',
                               facts={'process_validation': 'yes', 'software': 'unknown', 'outsourcing': 'no'})
    rows = {row.rule.clause: row for row in RuleEngine(bundle).evaluate([], context)}
    by_element = {check['element']: check['assessment_status'] for check in rows['7.5.6'].checks}
    assert by_element['过程确认触发条件'] == 'manual_review'
    assert by_element['过程评审'] == 'gap'
    assert by_element['软件使用前确认'] == 'pending_input'
    assert rows['4.1.5'].assessment_status == 'out_of_scope'
    prevention = {check['element']: check['assessment_status'] for check in rows['8.5.3'].checks}
    assert prevention['不利影响核查'] == 'manual_review'
    assert prevention['措施实施'] == 'gap'


def test_explicit_reference_uses_selected_version_and_target_content():
    source = doc('职责按照 QP-001 V1.0 执行。\n阶段由项目经理安排。')
    target = DocumentInput(2, 'd2', '受控程序.txt', 'procedure', '职责由研发主管承担。')
    review = {'documents': [{'file_uid': 'd2', 'metadata': {'revision': 'V1.0'}}], 'references': [
        {'source_file_uid': 'd1', 'number': 'QP-001', 'status': 'linked', 'target_file_uids': ['d2']} ]}
    engine = RuleEngine(rules())
    result = engine.evaluate([source, target], review=review)[0]
    assert result.assessment_status == 'evidence_found'
    assert {location['file_uid'] for location in result.checks[0]['locations']} == {'d1', 'd2'}
    review['documents'][0]['metadata']['revision'] = 'V2.0'
    assert engine.evaluate([source, target], review=review)[0].assessment_status == 'pending_input'


def test_partial_text_keeps_detected_evidence_and_marks_missing_unreadable():
    result = evaluate('责任由研发主管承担。', text_status='partial')
    assert result.assessment_status == 'unreadable'
    assert [row['assessment_status'] for row in result.checks] == ['evidence_found', 'unreadable']


def test_evidence_positions_are_bounded_with_total_count():
    result = evaluate('\n'.join(f'职责由项目负责人承担，活动序号为 {i}。' for i in range(20)))
    assert result.checks[0]['location_count'] == 20
    assert len(result.checks[0]['locations']) <= 3
