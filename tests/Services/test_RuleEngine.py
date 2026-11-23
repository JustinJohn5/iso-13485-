from pathlib import Path

import pytest

from App.Services.Rules.RuleEngine import DocumentInput, RuleEngine
from App.Services.Rules.RuleModels import CheckSpec, Rule, RuleSet
from App.Services.Rules.RuleSetLoader import RuleSetLoader


def make_rules() -> RuleSet:
    return RuleSet(
        rule_set_id="test",
        version="1.0",
        title="测试规则",
        rules=[
            Rule(
                rule_id="DOC-001",
                title="文件编号",
                clause="4.2.4",
                clause_title="文件控制",
                severity="major",
                check=CheckSpec(type="present", patterns=[r"文件编号\s*[:：]\s*QMS-\d+"]),
            )
        ],
    )


def test_rule_engine_reports_evidence_for_matching_document():
    engine = RuleEngine(make_rules())
    result = engine.evaluate([
        DocumentInput(1, "uid-1", "程序.docx", "procedure", "文件编号：QMS-001", char_count=13)
    ])

    assert len(result) == 1
    assert result[0].status == "pass"
    assert "QMS-001" in result[0].evidence


def test_rule_engine_skips_rules_for_unmatched_document_type():
    rules = make_rules()
    rules.rules[0].document_types = ["quality_manual"]
    result = RuleEngine(rules).evaluate([
        DocumentInput(1, "uid-1", "程序.docx", "procedure", "文件编号：QMS-001")
    ])

    assert result[0].status == "skipped"


def test_bundled_iso_rule_set_loads_and_compiles_patterns():
    project_root = Path(__file__).resolve().parents[2]
    loader = RuleSetLoader(project_root / "backend" / "App" / "Rules")

    rule_set = loader.get()

    assert rule_set.rule_set_id == "iso13485-core"
    assert len(rule_set.rules) >= 5


def test_adjacent_cover_fields_produce_distinct_focused_evidence():
    rules = RuleSetLoader(Path(__file__).resolve().parents[2] / 'backend/App/Rules').get()
    text = '某公司质量手册 文件编号：QM-01 版本：01 编制：审核：批准：2020年02月01日发布\n范围：医疗器械产品设计与生产。'
    results = RuleEngine(rules).evaluate([DocumentInput(1, 'u1', '质量手册.docx', 'quality_manual', text)])
    evidence = {item.rule.rule_id: item.evidence for item in results}
    assert evidence['DOC-001'] == '文件编号：QM-01'
    assert evidence['DOC-002'] == '版本：01'
    assert evidence['DOC-003'] == '批准'
    assert evidence['DOC-004'] == '2020年02月01日发布'
    assert len({evidence[f'DOC-00{i}'] for i in range(1, 5)}) == 4


@pytest.mark.parametrize('value', ['生效日期：2026-11-01', '发布日期：2026年11月01日', '2020年02月01日发布', '生效：2026/11/01', '实施日期：2026.11.01'])
def test_common_effective_and_issue_date_formats_are_recognized(value):
    rules = RuleSetLoader(Path(__file__).resolve().parents[2] / 'backend/App/Rules').get()
    result = RuleEngine(rules).evaluate([DocumentInput(1, 'u1', '文件.txt', 'other', value)])
    assert next(item for item in result if item.rule.rule_id == 'DOC-004').status == 'pass'
