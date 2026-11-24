"""整套版本的目录、快照、检查及真实归档内容。"""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

from docx import Document
import pytest

from App.Services.ManualSuites.Catalog import catalog
from App.Services.ManualSuites.Content import generate_items, import_items, revise_item
from App.Services.ManualSuites.Inspection import inspect_items
from App.Services.ManualSuites.Archive import build_archive
from App.Services.Rules.RuleSetLoader import RuleSetLoader
from App.Utils.Errors import ApiError


PARAMETERS = dict(company='测试组织', project='测试体系', product='测试产品', model='MODEL-A',
                  requirements='按实际质量体系填写，尚未确认的事实保留待确认项')


def test_generate_complete_selected_directory_with_independent_numbers_and_versions():
    items = generate_items([], [row['key'] for row in catalog()], PARAMETERS, 'A/0')
    assert len(items) >= 15
    assert len({row['number'] for row in items}) == len(items)
    manual = next(row for row in items if row['catalog_key'] == 'quality-manual')
    assert manual['file_version'] == 'A/0'
    assert '测试组织' in manual['text'] and 'MODEL-A' in manual['text']
    assert '待' in manual['text']
    later = generate_items([], ['quality-manual'], {**PARAMETERS, 'model': 'MODEL-B'}, 'A/1')
    assert later[0]['file_version'] == 'A/1'
    assert manual['file_version'] == 'A/0' and 'MODEL-B' not in manual['text']


def test_batch_generation_and_import_reject_duplicates_and_oversize_without_mutating():
    old = generate_items([], ['quality-manual'], PARAMETERS, '01')
    frozen = deepcopy(old)
    for keys in (['unknown'], ['quality-manual', 'quality-manual'], ['quality-manual']):
        with pytest.raises(ApiError):
            generate_items(old, keys, PARAMETERS, '02')
    with pytest.raises(ApiError):
        generate_items(old * 100, ['document-control'], PARAMETERS, '02')
    assert old == frozen


def upload(uid='file-1', text='文件编号：QM-01\n版本：B/2\n质量手册\n适用范围：医疗器械\n批准：待填写'):
    return SimpleNamespace(file_uid=uid, original_name='质量手册.txt', document_type='quality_manual',
                           extracted_text=text, sha256=uid, stored_name=uid + '.txt', size_bytes=len(text.encode()))


def test_import_freezes_text_and_preserves_file_version_separate_from_suite():
    source = upload()
    items = import_items([], [source])
    source.extracted_text = '后来改变'
    assert '质量手册' in items[0]['text']
    assert items[0]['file_version'] == 'B/2'
    assert items[0]['catalog_key'] == 'quality-manual'
    with pytest.raises(ApiError):
        import_items(items, [source])
    changed = revise_item(items, items[0]['id'], 'document-control', 'C/1')
    assert changed[0]['catalog_key'] == 'document-control'
    assert changed[0]['file_version'] == 'C/1'
    assert items[0]['file_version'] == 'B/2'


def test_generated_body_edit_updates_reader_and_word_without_changing_prior_snapshot(tmp_path):
    items = generate_items([], ['quality-manual'], PARAMETERS, '01')
    frozen = deepcopy(items)
    changed = revise_item(items, items[0]['id'], 'quality-manual', '01', sections={'s1': '已核实范围：测试医疗器械产品的生产与服务。'})
    assert items == frozen
    assert '已核实范围' in changed[0]['text']
    assert changed[0]['snapshot']['sections'][0]['body'].startswith('已核实范围')
    suite = SimpleNamespace(name='正文修订', version='01', revision=2, items=changed, inspection=None, suite_uid='edit')
    with ZipFile(BytesIO(build_archive(suite, tmp_path))) as archive:
        word = next(name for name in archive.namelist() if name.endswith('.docx'))
        assert '已核实范围' in '\n'.join(p.text for p in Document(BytesIO(archive.read(word))).paragraphs)
    imported = import_items([], [upload()])
    with pytest.raises(ApiError):
        revise_item(imported, imported[0]['id'], 'quality-manual', '01', sections={'s1': '不能改写导入原件'})


@pytest.mark.parametrize('key', ['quality-manual', 'document-control'])
def test_generated_file_version_can_differ_from_suite_and_is_consistent_in_word(tmp_path, key):
    items = generate_items([], [key], PARAMETERS, 'A/1')
    changed = revise_item(items, items[0]['id'], key, 'B/2')
    assert changed[0]['file_version'] == 'B/2'
    assert changed[0]['snapshot']['parameters']['version'] == 'B/2'
    assert '版本：B/2' in changed[0]['text'] and '版本：A/1' not in changed[0]['text']
    assert items[0]['file_version'] == 'A/1'
    suite = SimpleNamespace(name='独立文件版本', version='A/1', revision=2, items=changed, inspection=None, suite_uid='version')
    with ZipFile(BytesIO(build_archive(suite, tmp_path))) as archive:
        word = next(name for name in archive.namelist() if name.endswith('.docx'))
        assert 'B/2' in '\n'.join(p.text for p in Document(BytesIO(archive.read(word))).paragraphs)


def test_inspection_reports_missing_directory_references_and_unresolved_conflicts():
    rules = RuleSetLoader(Path(__file__).resolve().parents[2] / 'backend/App/Rules').get()
    items = import_items([], [upload(text='文件编号：QM-01\n版本：01\n质量手册\n适用范围：医疗器械\n按 QP-99 执行\n批准：待填写')])
    report = inspect_items(items, rules, '2026-11-24')
    assert report['missing_catalog']
    assert any(row['number'] == 'QP-99' and row['status'] == 'missing' for row in report['review']['references'])
    assert report['findings'] and report['rule_set']['version'] == '1.0.1'
    assert report['review']['as_of_date'] == '2026-11-24'
    with pytest.raises(ApiError):
        inspect_items([], rules, '2026-11-24')


def test_archive_contains_real_word_original_manifest_and_saved_report(tmp_path):
    original = upload()
    original.original_name = '体系:要求?.txt'
    (tmp_path / original.stored_name).write_bytes(original.extracted_text.encode('utf-8'))
    items = generate_items([], ['document-control'], PARAMETERS, 'A/0')
    items = import_items(items, [original])
    suite = SimpleNamespace(name='测试体系', version='A/0', revision=3, items=items,
                            inspection={'summary': '已保存检查'}, suite_uid='suite-1')
    with ZipFile(BytesIO(build_archive(suite, tmp_path))) as archive:
        names = archive.namelist()
        assert all('..' not in name and not any(char in name for char in '<>:"/\\|?*') for name in names)
        word = next(name for name in names if name.endswith('.docx'))
        content = '\n'.join(p.text for p in Document(BytesIO(archive.read(word))).paragraphs)
        assert '测试组织' in content and 'MODEL-A' in content
        assert any(name.endswith('.txt') and archive.read(name).decode() == original.extracted_text for name in names)
        assert 'A/0' in archive.read('目录.json').decode()
        assert '已保存检查' in archive.read('检查结果.json').decode()
    (tmp_path / original.stored_name).unlink()
    with pytest.raises(ApiError):
        build_archive(suite, tmp_path)
