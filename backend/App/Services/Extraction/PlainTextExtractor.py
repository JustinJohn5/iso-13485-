"""纯文本 / Markdown 抽取。"""

from __future__ import annotations

from pathlib import Path

from App.Services.Extraction.TextResult import TextResult

_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "utf-16")


def extract_text_file(path: Path) -> TextResult:
    """按常见编码依次尝试解码，全部失败时以替换模式兜底。"""
    raw = path.read_bytes()
    warnings: list[str] = []
    for encoding in _ENCODINGS:
        try:
            text = raw.decode(encoding)
            if encoding not in ("utf-8-sig", "utf-8"):
                warnings.append(f"文件按 {encoding} 编码解码")
            return TextResult(text=text, page_count=max(1, text.count("\n") // 45 + 1), warnings=warnings)
        except UnicodeDecodeError:
            continue
    text = raw.decode("utf-8", errors="replace")
    warnings.append("文件编码无法识别，部分字符可能显示异常")
    return TextResult(text=text, page_count=1, warnings=warnings)
