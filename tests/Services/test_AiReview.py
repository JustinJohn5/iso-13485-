"""AI 审阅的候选范围、引用校验和逐项合同测试。"""

from types import SimpleNamespace

import pytest

from App.Services.AiReview.EvidenceSearch import (
    build_candidate_snippets,
    validate_evidence_result,
)
from App.Services.AiReview.RequirementReview import (
    build_expected_elements,
    validate_requirement_result,
)
from App.Utils.Errors import ApiError


def sample_rule():
    return SimpleNamespace(
        rule_id="R-7.4.1",
        title="采购要求",
        clause="7.4.1",
        clause_title="采购过程",
        rationale="按供方能力和绩效控制采购。",
        suggestion="核对评价和再评价记录。",
        topics=["供方评价"],
        conditions=[],
        uncertainty="",
        evidence_requirements=["评价准则", "再评价记录"],
        check=SimpleNamespace(
            terms=[["供方评价", "供应商评估"], ["再评价", "重新评价"]],
            headings=[],
            patterns=[],
            documents=[],
            type="requirement",
        ),
    )


def test_candidate_snippets_keep_source_lines_and_rule_terms():
    text = "封面\n目录\n供方评价准则按季度执行。\n采购记录由质量部门复核。\n再评价结果保存五年。\n附件"

    snippets = build_candidate_snippets("file-1", text, sample_rule())

    assert snippets
    assert all(item["file_uid"] == "file-1" for item in snippets)
    assert any(item["start_line"] <= 3 <= item["end_line"] for item in snippets)
    assert any(item["start_line"] <= 5 <= item["end_line"] for item in snippets)
    assert "供方评价准则按季度执行。" in "\n".join(item["text"] for item in snippets)


def test_evidence_result_accepts_only_exact_quotes_from_known_snippets():
    snippets = [{
        "snippet_id": "S1", "file_uid": "file-1", "start_line": 3,
        "end_line": 4, "text": "供方评价准则按季度执行。\n采购记录由质量部门复核。",
    }]
    result = {
        "summary": "找到供方评价线索。",
        "claims": [{
            "signal": "support", "snippet_id": "S1",
            "quote": "供方评价准则按季度执行。", "reason": "说明评价安排。",
        }],
        "questions": [],
    }

    verified = validate_evidence_result(result, snippets)

    assert verified["claims"][0]["file_uid"] == "file-1"
    assert verified["claims"][0]["start_line"] == 3

    forged = {**result, "claims": [{**result["claims"][0], "quote": "所有供应商均已批准。"}]}
    with pytest.raises(ApiError):
        validate_evidence_result(forged, snippets)

    unknown = {**result, "claims": [{**result["claims"][0], "snippet_id": "S9"}]}
    with pytest.raises(ApiError):
        validate_evidence_result(unknown, snippets)


def test_candidate_and_citation_preserve_original_crlf_text():
    text = "目录\r\n供方评价准则按季度执行。\r\n再评价结果保存五年。\r\n附件"
    snippets = build_candidate_snippets("file-1", text, sample_rule())
    exact_quote = "供方评价准则按季度执行。\r\n再评价结果保存五年。"
    result = {
        "summary": "找到供方评价线索。",
        "claims": [{"signal": "support", "snippet_id": "S1", "quote": exact_quote,
                    "reason": "说明评价和再评价安排。"}],
        "questions": [],
    }

    verified = validate_evidence_result(result, snippets)

    assert exact_quote in snippets[0]["text"]
    assert verified["claims"][0]["start_line"] == 2
    assert verified["claims"][0]["end_line"] == 3
    normalized_quote = exact_quote.replace("\r\n", "\n")
    with pytest.raises(ApiError):
        validate_evidence_result({**result, "claims": [{**result["claims"][0], "quote": normalized_quote}]}, snippets)


def test_requirement_review_requires_every_rule_element_and_valid_quotes():
    rule = sample_rule()
    elements = build_expected_elements(rule)
    snippets = [{
        "snippet_id": "S1", "file_uid": "file-1", "start_line": 3,
        "end_line": 5, "text": "供方评价准则按季度执行。\n再评价结果保存五年。",
    }]
    result = {
        "summary": "已逐项检查候选片段。",
        "reviews": [
            {
                "element_id": elements[0]["element_id"],
                "status": "supporting_signal",
                "support": [{"snippet_id": "S1", "quote": "供方评价准则按季度执行。", "reason": "有评价安排。"}],
                "contrary": [], "rationale": "候选片段出现评价准则。", "questions": [],
            },
            {
                "element_id": elements[1]["element_id"],
                "status": "supporting_signal",
                "support": [{"snippet_id": "S1", "quote": "再评价结果保存五年。", "reason": "有再评价留存线索。"}],
                "contrary": [], "rationale": "候选片段出现再评价。", "questions": [],
            },
        ],
    }

    verified = validate_requirement_result(result, elements, snippets)

    assert len(verified["reviews"]) == len(elements)
    assert verified["reviews"][0]["support"][0]["start_line"] == 3
    with pytest.raises(ApiError):
        validate_requirement_result({**result, "reviews": result["reviews"][:1]}, elements, snippets)

    forged = {**result, "reviews": [
        {**result["reviews"][0], "support": [{**result["reviews"][0]["support"][0], "quote": "供应商已全部批准。"}]},
        result["reviews"][1],
    ]}
    with pytest.raises(ApiError):
        validate_requirement_result(forged, elements, snippets)


def test_not_found_status_is_scoped_to_candidates_and_cannot_claim_document_absence():
    elements = build_expected_elements(sample_rule())
    result = {
        "summary": "仅依据候选片段整理。",
        "reviews": [{
            "element_id": item["element_id"], "status": "not_found_in_candidates",
            "support": [], "contrary": [],
            "rationale": "本次检索的候选片段中未找到相关表述。",
            "questions": ["请人工检查原文件其余部分。"],
        } for item in elements],
    }

    verified = validate_requirement_result(result, elements, [])

    assert all(item["status"] == "not_found_in_candidates" for item in verified["reviews"])
    overclaim = {**result, "reviews": [
        {**item, "rationale": "该文件没有此项要求。"} for item in result["reviews"]
    ]}
    with pytest.raises(ApiError):
        validate_requirement_result(overclaim, elements, [])

    overclaim_summary = {**result, "summary": "该文件没有相关要求。"}
    with pytest.raises(ApiError):
        validate_requirement_result(overclaim_summary, elements, [])
