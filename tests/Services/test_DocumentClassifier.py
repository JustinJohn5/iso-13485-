"""自动分类及手动覆盖的回归测试，不连接数据库。"""
from pathlib import Path

import pytest

from App.Services.DocumentClassifier import detect_document_type, resolve_document_type
from App.Services.Rules.RuleSetLoader import RuleSetLoader
from App.Utils.Errors import ApiError


@pytest.fixture
def rules():
    return RuleSetLoader(Path(__file__).resolve().parents[2] / 'backend/App/Rules').get()


@pytest.mark.parametrize(('name', 'text', 'expected'), [
    ('QM-01 Rev.01 质量手册.docx', '内容', 'quality_manual'),
    ('未命名.txt', '某公司\n质 量 管 理 体 系 手 册\n文件编号 QMS-001', 'quality_manual'),
    ('Quality Manual.pdf', 'scope of medical devices', 'quality_manual'),
    ('内部审核程序.docx', '审核发现和纠正措施', 'internal_audit'),
    ('管理评审记录.xlsx', '评审输入和输出', 'management_review'),
    ('风险管理报告.docx', '风险分析及剩余风险', 'risk_management'),
    ('采购程序.docx', '采购程序及供应商控制', 'purchasing'),
    ('通用程序.docx', '操作方法\n流程\n职责\n记录\n目的\n注意事项', 'procedure'),
    ('材料.txt', '仅为一段不包含质量体系类别信息的说明。', 'other'),
    ('质量手册及风险管理.docx', '质量手册\n风险管理', 'other'),
])
def test_classification_handles_names_content_and_ambiguity(rules, name, text, expected):
    assert detect_document_type(name, text, rules).type == expected


def test_manual_type_overrides_automatic_detection(rules):
    kind, detection = resolve_document_type('procedure', '质量手册.docx', '质量手册', rules)
    assert kind == 'procedure'
    assert detection.type == 'quality_manual'


def test_invalid_type_is_rejected(rules):
    with pytest.raises(ApiError) as caught:
        resolve_document_type('invalid', '文件.txt', '内容', rules)
    assert caught.value.code == 1001
