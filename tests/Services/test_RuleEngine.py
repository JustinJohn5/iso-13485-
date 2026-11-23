from pathlib import Path

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
