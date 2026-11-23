"""模拟内审基于已保存事实，不把文本线索转换为合规结论。"""
from io import BytesIO

from docx import Document

from App.Services.Audit.QuestionBuilder import build_questions, export_questions


def finding(status='fail'):
    return {'status': status, 'title': '文件应包含版本或修订标识', 'clause': '4.2.4',
            'evidence': '版本信息尚未检出', 'suggestion': '核对当前受控版本', 'document': '采购程序.txt'}


def test_failed_and_passed_rules_have_distinct_questions_and_skipped_ignored():
    report = build_questions('test-run', [finding(), finding(), finding('pass'), finding('skipped')], None)
    assert report['summary'] == {'gap': 1, 'reference': 0, 'conflict': 0, 'verification': 1}
    assert '实际执行记录' in report['questions'][1]['question']
    assert report['questions'][0]['evidence'] == '版本信息尚未检出'
    assert '不构成' in report['disclaimer']


def test_missing_references_and_confirmed_conflicts_stay_visible_and_excluded_versions_ignored():
    review = {'documents': [{'file_uid': 'a', 'name': '手册'}, {'file_uid': 'old', 'name': '旧程序'}],
              'version_groups': [{'file_uids': ['old', 'new'], 'decision': {'file_uid': 'new'}}],
              'references': [{'source_file_uid': 'a', 'number': 'QR-01', 'status': 'missing', 'quote': '引用 QR-01'},
                             {'source_file_uid': 'old', 'number': 'QR-02', 'status': 'missing', 'quote': '旧版引用 QR-02'},
                             {'source_file_uid': 'a', 'number': 'QR-03', 'status': 'linked', 'quote': '已关联 QR-03'}],
              'requirement_conflicts': [{'number': 'QR-01', 'field': '保存期限', 'decision': {'file_uid': 'a'},
                                         'facts': [{'file_uid': 'a', 'quote': '3年'}, {'file_uid': 'new', 'quote': '5年'}]}]}
    report = build_questions('test-run', [], review)
    assert report['summary']['reference'] == 1 and report['summary']['conflict'] == 1
    assert 'QR-02' not in str(report) and 'QR-03' not in str(report)
    assert '不表示文件不存在' in report['questions'][0]['action']
    assert '3年' in report['questions'][1]['evidence'] and '5年' in report['questions'][1]['evidence']


def test_export_contains_questions_and_manual_followup_fields():
    report = build_questions('test-run', [finding()], None)
    text = '\n'.join(item.text for item in Document(BytesIO(export_questions(report))).paragraphs)
    assert '审核提问' in text and '版本信息尚未检出' in text
    assert '责任人：待填写' in text and '有效性验证' in text and 'test-run' in text
