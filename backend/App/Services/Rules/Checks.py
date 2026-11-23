"""规则判定原子能力：纯函数，便于单元测试。

所有判定只依赖抽取出的纯文本，不访问数据库。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from App.Services.Rules.RuleModels import CheckSpec
from App.Services.Rules.TextNormalizer import (
    compress,
    heading_lines,
    normalize_text,
    snippet,
)
from App.Utils.TimeUtils import now, parse_date

_REGEX_CACHE: dict[str, re.Pattern[str]] = {}


def compile_pattern(pattern: str) -> re.Pattern[str]:
    """编译并缓存正则（大小写不敏感、多行）。"""
    cached = _REGEX_CACHE.get(pattern)
    if cached is None:
        cached = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
        _REGEX_CACHE[pattern] = cached
    return cached


@dataclass(frozen=True)
class CheckOutcome:
    """单条规则的判定结果。"""

    passed: bool
    evidence: str
    detail: str


def _as_outcome(passed: bool, evidence: str, detail: str) -> CheckOutcome:
    return CheckOutcome(passed=passed, evidence=compress(evidence, 300), detail=detail)


def check_present(text: str, spec: CheckSpec) -> CheckOutcome:
    """要求文本中出现指定模式，至少 min_matches 处。"""
    text = normalize_text(text)
    hits: set[tuple[int, int]] = set()
    for pattern in spec.patterns:
        for match in compile_pattern(pattern).finditer(text):
            hits.add((match.start(), match.end()))
    if len(hits) >= spec.min_matches:
        start, end = min(hits)
        return _as_outcome(True, text[start:end], f"命中 {len(hits)} 处相关内容")
    return _as_outcome(
        False,
        "",
        f"未检出要求的内容（需至少 {spec.min_matches} 处，实际 {len(hits)} 处）",
    )


def check_absent(text: str, spec: CheckSpec) -> CheckOutcome:
    """禁止出现的模式（如作废标准版本）。"""
    for pattern in spec.patterns:
        match = compile_pattern(pattern).search(text)
        if match:
            return _as_outcome(
                False,
                snippet(text, match.start(), match.end()),
                f"检出不应出现的内容：{compress(match.group(0), 60)}",
            )
    return _as_outcome(True, "", "未检出作废/禁止内容")


def check_section(text: str, spec: CheckSpec) -> CheckOutcome:
    """要求存在指定章节标题（同义词任一命中即可）。"""
    titles = [re.sub(r"\s+", "", item).lower() for item in spec.headings if item.strip()]
    for line in heading_lines(text):
        normalized = re.sub(r"\s+", "", line).lower()
        for title in titles:
            if title in normalized:
                return _as_outcome(True, line, f"检出章节标题：{line}")
    return _as_outcome(False, "", f"未检出章节：{' / '.join(spec.headings[:3])}")


def check_all_terms(text: str, spec: CheckSpec) -> CheckOutcome:
    """要求命中词组集合，默认全部命中，可用 min_groups 放宽。"""
    lowered = text.lower()
    matched: list[str] = []
    missing: list[str] = []
    for group in spec.terms:
        hit = next((term for term in group if term.lower() in lowered), None)
        if hit:
            matched.append(hit)
        else:
            missing.append(group[0] if group else "")
    required = spec.min_groups if spec.min_groups is not None else len(spec.terms)
    if len(matched) >= required:
        return _as_outcome(
            True, "、".join(matched), f"命中 {len(matched)}/{len(spec.terms)} 个要素"
        )
    return _as_outcome(
        False,
        "",
        f"缺少要素：{'、'.join(item for item in missing if item)[:200]}",
    )


def check_date(text: str, spec: CheckSpec) -> CheckOutcome:
    """校验文中日期的有效性与时效。"""
    for pattern in spec.patterns:
        match = compile_pattern(pattern).search(text)
        if not match:
            continue
        raw_value = match.group(1) if match.groups() else match.group(0)
        parsed = parse_date(raw_value)
        if parsed is None:
            return _as_outcome(False, snippet(text, match.start(), match.end()), "日期格式无法识别")
        today = now()
        if spec.not_future and parsed > today:
            return _as_outcome(
                False, snippet(text, match.start(), match.end()), f"日期晚于当前日期：{raw_value}"
            )
        if spec.max_age_days is not None:
            age_days = (today - parsed).days
            if age_days > spec.max_age_days:
                return _as_outcome(
                    False,
                    snippet(text, match.start(), match.end()),
                    f"日期已超过 {spec.max_age_days} 天：{raw_value}",
                )
        return _as_outcome(True, snippet(text, match.start(), match.end()), f"日期有效：{raw_value}")
    return _as_outcome(False, "", "未检出可识别的日期")


def check_length(text: str, spec: CheckSpec) -> CheckOutcome:
    """校验可抽取文本量，识别空文件或扫描件。"""
    length = len(text.strip())
    if length >= spec.min_chars:
        return _as_outcome(True, f"可抽取文本 {length} 字", f"文本量充足（{length} 字）")
    return _as_outcome(
        False,
        "",
        f"可抽取文本仅 {length} 字，少于要求的 {spec.min_chars} 字（可能为扫描件或空文件）",
    )


def find_missing_documents(present_types: set[str], spec: CheckSpec) -> list[str]:
    """体系完整性：返回规则要求但未上传的文档类型。"""
    return [doc_type for doc_type in spec.documents if doc_type not in present_types]
