"""模板边界、参数联动、快照隔离与真实 DOCX 内容回归。"""
from copy import deepcopy
from io import BytesIO

from docx import Document
import pytest

from App.Constants.AuthoringLimits import MAX_REQUIREMENTS_CHARS, MAX_SECTION_CHARS
from App.Services.Authoring.TemplateLibrary import TEMPLATES, build_snapshot, edit_sections, search_templates
from App.Services.Authoring.WordExport import export_word
from App.Utils.Errors import ApiError


def parameters():
    return {'company': '测试组织', 'project': '净化项目', 'product': '测试产品', 'model': 'MODEL-A',
            'number': 'WI-01', 'version': 'A/0', 'requirements': '依据经确认的产品技术要求逐项检验，不编造数值。'}


def test_catalog_search_and_copy_isolation():
    assert [row['id'] for row in search_templates('成品 检验', '技术文件')] == ['finished-inspection']
    assert search_templates('不存在的模板') == []
    result = search_templates()
    result[0]['fields'].clear()
    assert search_templates()[0]['fields']


@pytest.mark.parametrize('template_id', [item['id'] for item in TEMPLATES])
def test_templates_render_known_parameters_without_claiming_approval(template_id):
    snapshot = build_snapshot(template_id, parameters())
    assert snapshot['status'] == 'draft'
    assert '{product}' not in str(snapshot)
    assert 'MODEL-A' in str(snapshot['sections'])


@pytest.mark.parametrize('changes', [{'product': ''}, {'model': 'a' * 121}, {'extra': 'unsupported'}, {'product': '\x00非法'}])
def test_invalid_values_are_rejected(changes):
    with pytest.raises(ApiError):
        build_snapshot('finished-inspection', {**parameters(), **changes})


def test_parameter_regeneration_updates_all_template_occurrences_and_preserves_old_snapshot():
    previous = build_snapshot('finished-inspection', parameters())
    frozen = deepcopy(previous)
    new = build_snapshot('finished-inspection', {**parameters(), 'product': '新版产品', 'model': 'MODEL-B'})
    assert 'MODEL-A' not in str(new['sections'])
    assert sum('MODEL-B' in item['body'] for item in new['sections']) >= 3
    assert previous == frozen


def test_manual_edits_do_not_mutate_prior_snapshot_and_validate_ids():
    snapshot = build_snapshot('market-research', parameters())
    updated = edit_sections(snapshot, {'s2': '已核实的调研输入'})
    assert updated['sections'][1]['body'] == '已核实的调研输入'
    assert snapshot['sections'][1]['body'] != updated['sections'][1]['body']
    assert updated['origin'] == 'manual'
    for value in ({'no-such-section': '内容'}, {'s1': ''}, {'s1': '超' * (MAX_SECTION_CHARS + 1)}):
        with pytest.raises(ApiError):
            edit_sections(snapshot, value)


def test_word_has_real_document_structure_and_draft_marking():
    snapshot = build_snapshot('finished-inspection', parameters())
    document = Document(BytesIO(export_word(snapshot, 3)))
    text = '\n'.join(paragraph.text for paragraph in document.paragraphs)
    assert '成品检验规程' in text and '草稿' in text and '不作为产品放行' in text
    assert 'MODEL-A' in text
    assert len(document.tables) == 1
    assert '3 / 1.0' in text
    assert document.tables[0].rows[1].cells[1].text == '草稿 r3'


@pytest.mark.parametrize('template_id', [item['id'] for item in TEMPLATES])
def test_long_requirements_and_sections_survive_generation_edit_and_word_export(template_id):
    requirements = '资' * (MAX_REQUIREMENTS_CHARS - 4) + '资料末尾'
    snapshot = build_snapshot(template_id, {**parameters(), 'requirements': requirements})
    assert snapshot['parameters']['requirements'] == requirements
    assert requirements in snapshot['sections'][1]['body']
    body = '文' * (MAX_SECTION_CHARS - 4) + '章节末尾'
    updated = edit_sections(snapshot, {'s2': body})
    assert updated['sections'][1]['body'] == body
    assert snapshot['sections'][1]['body'] != body
    document = Document(BytesIO(export_word(updated, 2)))
    assert body in [paragraph.text for paragraph in document.paragraphs]
    with pytest.raises(ApiError):
        build_snapshot(template_id, {**parameters(), 'requirements': requirements + '超'})
