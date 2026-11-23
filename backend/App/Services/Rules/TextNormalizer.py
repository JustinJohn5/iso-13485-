"""文本归一化与证据片段工具。"""

from __future__ import annotations

import re

_HEADING_NUMBER_PATTERN = re.compile(
    r"^\s*(?:第[一二三四五六七八九十百]+[章节条款]|[一二三四五六七八九十]+[、.．]|"
    r"[（(][一二三四五六七八九十0-9]+[)）]|[0-9]+(?:\.[0-9]+){0,3}[、.．\s])"
)
_WHITESPACE_PATTERN = re.compile(r"[ \t\u3000\xa0]+")


def normalize_text(raw: str) -> str:
    """统一换行、全角空格与多余空白，便于规则匹配。"""
    text = (raw or "").replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u3000", " ")
    lines = [_WHITESPACE_PATTERN.sub(" ", line).strip() for line in text.split("\n")]
    # 连续空行压缩为一行
    compact: list[str] = []
    for line in lines:
        if line or (compact and compact[-1]):
            compact.append(line)
    return "\n".join(compact).strip()


def compress(text: str, limit: int = 200) -> str:
    """压缩空白并截断，用于证据展示。"""
    value = _WHITESPACE_PATTERN.sub(" ", (text or "").replace("\n", " ")).strip()
    return value[:limit]


def snippet(text: str, start: int, end: int, radius: int = 40) -> str:
    """截取命中位置附近的上下文作为证据。"""
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return compress(text[left:right], 220)


def strip_heading_number(line: str) -> str:
    """去掉行首章节编号，便于标题比对。"""
    return _HEADING_NUMBER_PATTERN.sub("", line).strip()


def heading_lines(text: str, max_length: int = 48) -> list[str]:
    """提取可能的标题行（短行且去掉编号后非空）。"""
    result: list[str] = []
    for line in text.split("\n"):
        raw = line.strip()
        if not raw or len(raw) > max_length:
            continue
        cleaned = strip_heading_number(raw)
        if cleaned and len(cleaned) >= 2:
            result.append(cleaned)
    return result


def key_value_pairs(text: str, labels: list[str], max_distance: int = 24) -> list[tuple[str, str]]:
    """在同一行内按标签提取键值，如「文件编号：QP-01」。"""
    pairs: list[tuple[str, str]] = []
    for line in text.split("\n"):
        for label in labels:
            index = line.find(label)
            if index < 0:
                continue
            tail = line[index + len(label) :][:max_distance]
            value = tail.strip(" :：\t-—|")
            if value and not any(ch.isalnum() or "\u4e00" <= ch <= "\u9fff" for ch in value[:1]):
                value = ""
            pairs.append((label, value))
            break
    return pairs
