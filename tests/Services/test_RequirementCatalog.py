"""共用条款目录：完整性、概念拆分和调用方隔离。"""

import json
from copy import deepcopy

import pytest

from App.Services.Rules import RequirementCatalog as catalog_module
from App.Services.Rules.RequirementCatalog import load_catalog, requirements_for_template
from App.Utils.Errors import ApiError


TEMPLATE_IDS = {
    'quality-manual', 'quality-policy', 'document-control', 'record-control',
    'management-review', 'training', 'infrastructure', 'risk-management',
    'purchasing', 'production', 'traceability', 'monitoring', 'complaints',
    'internal-audit', 'nonconformity', 'corrective-action', 'record-forms',
    'design-plan', 'finished-inspection', 'market-research',
}
CONDITIONS = {
    'design', 'sterile', 'implant', 'installation', 'servicing', 'outsourcing',
    'software', 'cleaning', 'process_validation', 'customer_property',
}


def expected_clauses():
    clauses = [f'4.1.{i}' for i in range(1, 7)] + [f'4.2.{i}' for i in range(1, 6)]
    clauses += ['5.1', '5.2', '5.3', '5.4.1', '5.4.2']
    clauses += [f'5.5.{i}' for i in range(1, 4)] + [f'5.6.{i}' for i in range(1, 4)]
    clauses += ['6.1', '6.2', '6.3', '6.4.1', '6.4.2', '7.1']
    clauses += [f'7.2.{i}' for i in range(1, 4)] + [f'7.3.{i}' for i in range(1, 11)]
    clauses += [f'7.4.{i}' for i in range(1, 4)] + [f'7.5.{i}' for i in range(1, 9)]
    clauses += ['7.5.9.1', '7.5.9.2', '7.5.10', '7.5.11', '7.6', '8.1']
    clauses += [f'8.2.{i}' for i in range(1, 7)] + [f'8.3.{i}' for i in range(1, 5)]
    clauses += ['8.4', '8.5.1', '8.5.2', '8.5.3']
    return set(clauses)


def test_catalog_covers_all_72_leaf_clauses_with_traceable_sources():
    catalog = load_catalog()
    assert catalog['version'] == '2.0.0'
    assert catalog['source']['standard'] == 'ISO 13485:2016'
    assert len(catalog['requirements']) == 72
    assert {row['clause'] for row in catalog['requirements']} == expected_clauses()
    assert len({row['rule_id'] for row in catalog['requirements']}) == 72
    for row in catalog['requirements']:
        assert row['rule_id'] == f"R-{row['clause']}"
        assert row['title'] and row['generation'] and row['evidence']
        assert row['clause'] in row['source'] and '物理页' in row['source']
        assert isinstance(row['uncertainty'], str)
        assert row['terms'] and all(group and all(term.strip() for term in group)
                                    for group in row['terms'])
        assert row['topics'] and all(len(topic) >= 2 for topic in row['topics'])
        assert set(row['templates']) <= TEMPLATE_IDS
        assert set(row['conditions']) <= CONDITIONS


def test_all_existing_templates_have_specific_requirements():
    for template_id in TEMPLATE_IDS:
        rows = requirements_for_template(template_id)
        assert rows, template_id
        assert all(template_id in row['templates'] for row in rows)
    assert {row['clause'] for row in requirements_for_template('document-control')} == {'4.2.4'}
    assert {row['clause'] for row in requirements_for_template('management-review')} == {
        '5.6.1', '5.6.2', '5.6.3',
    }
    assert '7.3.2' in {row['clause'] for row in requirements_for_template('design-plan')}
    assert '8.2.4' not in {row['clause'] for row in requirements_for_template('production')}


def test_catalog_and_template_results_are_independent_deep_copies():
    first = load_catalog()
    first['source']['standard'] = '被修改'
    first['requirements'][0]['terms'][0].append('被修改')
    assert load_catalog()['source']['standard'] == 'ISO 13485:2016'
    assert '被修改' not in load_catalog()['requirements'][0]['terms'][0]
    rows = requirements_for_template('design-plan')
    rows[0]['terms'][0].append('被修改')
    assert all('被修改' not in group for row in requirements_for_template('design-plan')
               for group in row['terms'])


@pytest.mark.parametrize('template_id', ['unknown', '', '../core', None, [], 123])
def test_unknown_or_invalid_template_is_a_parameter_error(template_id):
    with pytest.raises(ApiError) as error:
        requirements_for_template(template_id)
    assert error.value.code == 1001


def test_management_review_has_twelve_distinct_input_groups():
    row = next(row for row in load_catalog()['requirements'] if row['clause'] == '5.6.2')
    assert len(row['terms']) == 12
    for concept in ['反馈', '投诉', '监管报告', '审核', '过程监测', '产品监测',
                    '纠正措施', '预防措施', '以前评审', '体系变更', '改进建议', '法规']:
        assert any(any(concept in term for term in group) for group in row['terms']), concept


def test_design_planning_six_categories_are_not_one_any_term_group():
    row = next(row for row in load_catalog()['requirements'] if row['clause'] == '7.3.2')
    assert len(row['terms']) >= 6
    for concept in ['阶段', '评审', '验证', '确认', '转换', '职责', '追溯', '资源', '能力']:
        assert any(any(concept in term for term in group) for group in row['terms']), concept


def test_translation_uncertainties_are_preserved():
    rows = {row['clause']: row for row in load_catalog()['requirements']}
    assert '触发条件' in rows['7.5.6']['uncertainty']
    assert '人工' in rows['7.5.6']['uncertainty']
    assert '纠正措施' in rows['8.5.3']['uncertainty']


def test_compound_conditions_do_not_exempt_the_whole_clause():
    rows = {row['clause']: row for row in load_catalog()['requirements']}
    for clause in ('6.4.2', '7.5.6'):
        assert rows[clause]['conditions'] == []
        assert '分别' in rows[clause]['uncertainty']
        assert '人工' in rows[clause]['uncertainty']


@pytest.mark.parametrize('damage', [
    'duplicate', 'missing_clause', 'bad_condition', 'empty_group', 'blank_term',
    'bad_template', 'bad_type', 'missing_source', 'missing_uncertainty', 'bad_version',
    'unknown_field', 'wrong_rule_id', 'blank_generation', 'empty_topics',
])
def test_catalog_rejects_damaged_configuration(tmp_path, monkeypatch, damage):
    payload = deepcopy(load_catalog())
    row = payload['requirements'][0]
    if damage == 'duplicate':
        payload['requirements'][1] = deepcopy(row)
    elif damage == 'missing_clause':
        payload['requirements'].pop()
    elif damage == 'bad_condition':
        row['conditions'] = ['unapproved']
    elif damage == 'empty_group':
        row['terms'] = [[]]
    elif damage == 'blank_term':
        row['terms'] = [[' ']]
    elif damage == 'bad_template':
        row['templates'] = ['unapproved']
    elif damage == 'bad_type':
        row['document_types'] = ['unapproved']
    elif damage == 'missing_source':
        row['source'] = ''
    elif damage == 'missing_uncertainty':
        next(item for item in payload['requirements']
             if item['clause'] == '7.5.6')['uncertainty'] = ''
    elif damage == 'bad_version':
        payload['version'] = '1.0.0'
    elif damage == 'unknown_field':
        row['typo'] = '未知字段'
    elif damage == 'wrong_rule_id':
        row['rule_id'] = 'R-4.1.2'
    elif damage == 'blank_generation':
        row['generation'] = ' '
    elif damage == 'empty_topics':
        row['topics'] = []
    path = tmp_path / 'Iso13485.json'
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    monkeypatch.setattr(catalog_module, 'CATALOG_PATH', path)
    with pytest.raises(ApiError) as error:
        load_catalog()
    assert error.value.code == 1305


@pytest.mark.parametrize('text', ['{', '[]', 'null'])
def test_invalid_json_or_root_has_a_clear_error(tmp_path, monkeypatch, text):
    path = tmp_path / 'Iso13485.json'
    path.write_text(text, encoding='utf-8')
    monkeypatch.setattr(catalog_module, 'CATALOG_PATH', path)
    with pytest.raises(ApiError) as error:
        load_catalog()
    assert error.value.code == 1305


def test_missing_file_has_a_clear_error(tmp_path, monkeypatch):
    monkeypatch.setattr(catalog_module, 'CATALOG_PATH', tmp_path / 'missing.json')
    with pytest.raises(ApiError) as error:
        load_catalog()
    assert error.value.code == 1305
