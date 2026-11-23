"""文件类型识别：优先文件名和标题，正文多线索补充，歧义时不猜测。"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path

from App.Services.Rules.RuleModels import RuleSet
from App.Utils.Errors import ApiError


@dataclass(frozen=True)
class TypeDetection:
    type: str
    label: str
    source: str
    confidence: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text)).casefold()


def detect_document_type(name: str, text: str, rule_set: RuleSet) -> TypeDetection:
    """类型词来自规则包；重复出现同一词不会无限增加置信度。"""
    filename = _compact(Path(name).stem)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    headings = [_compact(line) for line in lines[:16] if len(line) <= 80]
    body = _compact(text[:30000])
    scores: list[tuple[int, str, str]] = []
    for item in rule_set.document_types:
        if item.type == "other":
            continue
        words = set(_compact(word) for word in [item.label, *item.keywords] if word.strip())
        if item.type == "quality_manual":
            words.update({"质量管理手册", "质量管理体系手册"})
        name_hits = [word for word in words if word in filename]
        title_hits = [word for word in words if any(word in line for line in headings)]
        body_hits = [word for word in words if word in body]
        score = (12 if name_hits else 0) + (6 if title_hits else 0) + min(len(body_hits), 3)
        source = "filename" if name_hits else "content"
        if score >= 6 or len(body_hits) >= 2:
            scores.append((score, item.type, source))

    # 专用文档名称中经常同时包含“程序”，避免被通用程序类型抢占。
    strongest_specific = max((score for score, kind, _ in scores if kind != "procedure"), default=0)
    scores = [entry for entry in scores if entry[1] != "procedure" or entry[0] > strongest_specific]
    scores.sort(reverse=True)
    if not scores:
        return TypeDetection("other", rule_set.document_type_label("other"), "unrecognized", "low", "线索不足，请手动确认文件类型")
    if len(scores) > 1 and scores[0][0] - scores[1][0] < 2:
        return TypeDetection("other", rule_set.document_type_label("other"), "ambiguous", "low", "存在多种类型线索，请手动确认")
    score, kind, source = scores[0]
    return TypeDetection(kind, rule_set.document_type_label(kind), source,
                         "high" if score >= 12 else "medium",
                         "根据文件名识别" if source == "filename" else "根据正文标题和关键词识别")


def resolve_document_type(requested: str, name: str, text: str, rule_set: RuleSet) -> tuple[str, TypeDetection]:
    """手动选择优先；auto 才应用自动识别结果。"""
    valid_types = {item.type for item in rule_set.document_types}
    if requested != "auto" and requested not in valid_types:
        raise ApiError(1001, "请选择有效的文件类型")
    detection = detect_document_type(name, text, rule_set)
    return (detection.type if requested == "auto" else requested), detection
