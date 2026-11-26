"""候选片段检索及模型引用校验的共用逻辑。"""

from __future__ import annotations

from collections.abc import Iterable

from App.Utils.Errors import ApiError

MAX_CANDIDATES = 12
MAX_SNIPPET_CHARS = 2400
_LINE_BREAKS = "\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029"


def _line_break_count(value: str) -> int:
    """统计字符串中的原始换行边界，包括 CRLF 和 Unicode 行分隔符。"""
    if not value:
        return 0
    return len(value.splitlines()) - int(value[-1] not in _LINE_BREAKS)


def _line_body(value: str) -> str:
    """去掉一行末尾的分隔符用于搜索，保留原文另行传递。"""
    if value.endswith("\r\n"):
        return value[:-2]
    if value and value[-1] in _LINE_BREAKS:
        return value[:-1]
    return value


def rule_search_terms(rule) -> list[str]:
    """从当前规则提取可用于字面检索的主题和同义词。"""
    values: list[str] = [rule.rule_id, rule.clause, rule.title, rule.clause_title]
    check = rule.check
    for group in check.terms:
        values.extend(group)
    values.extend(check.headings)
    values.extend(rule.topics)
    values.extend(rule.conditions)
    values.extend(rule.evidence_requirements)
    values.extend((rule.rationale, rule.suggestion))

    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        term = " ".join(str(raw).split()).strip()
        key = term.casefold()
        if len(term) >= 2 and key not in seen:
            seen.add(key)
            result.append(term)
    return result


def build_candidate_snippets(
    file_uid: str,
    text: str,
    rule,
    *,
    max_candidates: int = MAX_CANDIDATES,
    context_lines: int = 1,
) -> list[dict]:
    """按规则词组取邻近原文，保留抽取文本的 1 起始行号。"""
    lines = text.splitlines(keepends=True)
    bodies = [_line_body(line) for line in lines]
    if not lines or not text.strip():
        return []

    terms = rule_search_terms(rule)
    scored: list[tuple[int, int, list[str]]] = []
    for index, line in enumerate(bodies):
        lowered = line.casefold()
        hits = [term for term in terms if term.casefold() in lowered]
        if hits:
            scored.append((len(hits), index, hits))

    selected = sorted(scored, key=lambda item: (-item[0], item[1]))[:max_candidates]
    windows = sorted(
        (max(0, index - context_lines), min(len(lines) - 1, index + context_lines), index, hits)
        for _, index, hits in selected
    )
    merged: list[tuple[int, int, list[tuple[int, list[str]]]]] = []
    for start, end, hit_line, hits in windows:
        if merged and start <= merged[-1][1] + 1:
            old_start, old_end, old_hits = merged[-1]
            merged[-1] = (old_start, max(old_end, end), old_hits + [(hit_line, hits)])
        else:
            merged.append((start, end, [(hit_line, hits)]))

    snippets: list[dict] = []
    for start, end, hit_lines in merged:
        content = "".join(lines[start:end + 1])
        snippet_start = start + 1
        if len(content) > MAX_SNIPPET_CHARS:
            hit_line, hit_terms = max(hit_lines, key=lambda item: len(item[1]))
            line_start = sum(len(line) for line in lines[start:hit_line])
            line = bodies[hit_line]
            term_position = next((line.casefold().find(term.casefold()) for term in hit_terms
                                  if line.casefold().find(term.casefold()) >= 0), 0)
            anchor = line_start + term_position
            clip_start = max(0, min(anchor - MAX_SNIPPET_CHARS // 2, len(content) - MAX_SNIPPET_CHARS))
            snippet_start += _line_break_count(content[:clip_start])
            content = content[clip_start:clip_start + MAX_SNIPPET_CHARS]
        end_line = snippet_start + _line_break_count(content)
        if content and content[-1] in _LINE_BREAKS:
            end_line -= 1
        snippets.append({
            "snippet_id": f"S{len(snippets) + 1}",
            "file_uid": file_uid,
            "start_line": snippet_start,
            "end_line": max(snippet_start, end_line),
            "text": content,
        })
    return snippets


def verify_citations(citations: Iterable[dict], snippets: list[dict]) -> list[dict]:
    """拒绝未知片段和不能在原文候选中逐字找到的摘录。"""
    by_id = {item["snippet_id"]: item for item in snippets}
    verified: list[dict] = []
    for citation in citations:
        snippet = by_id.get(citation["snippet_id"])
        quote = citation["quote"]
        if snippet is None or not quote or quote not in snippet["text"]:
            raise ApiError(1402, "AI 引用无法与本次文件的抽取原文精确匹配，请重新审阅")
        offset = snippet["text"].find(quote)
        line = snippet["start_line"] + _line_break_count(snippet["text"][:offset])
        end_line = line + _line_break_count(quote)
        if quote and quote[-1] in _LINE_BREAKS:
            end_line -= 1
        verified.append({
            **citation,
            "file_uid": snippet["file_uid"],
            "start_line": line,
            "end_line": max(line, end_line),
        })
    return verified
