"""Word（.docx）文本抽取：段落 + 表格。"""

from __future__ import annotations

from pathlib import Path

from docx import Document

from App.Services.Extraction.TextResult import TextResult
from App.Utils.Errors import ApiError
from App.Utils.Logger import get_logger

logger = get_logger(__name__)

MAX_PARAGRAPHS = 8000


def extract_docx(path: Path) -> TextResult:
    """抽取段落与表格文本，按阅读顺序拼接。"""
    try:
        document = Document(str(path))
    except Exception as exc:  # noqa: BLE001
        logger.warning("DOCX 打开失败：%s", exc)
        raise ApiError(1204, "Word 文档无法解析，可能已损坏") from exc

    warnings: list[str] = []
    lines: list[str] = []

    for index, paragraph in enumerate(document.paragraphs):
        if index >= MAX_PARAGRAPHS:
            warnings.append(f"段落数超过 {MAX_PARAGRAPHS}，仅判定前 {MAX_PARAGRAPHS} 段")
            break
        text = (paragraph.text or "").strip()
        if text:
            lines.append(text)

    for table_index, table in enumerate(document.tables):
        if table_index >= 50:
            warnings.append("表格数量超过 50，仅判定前 50 个表格")
            break
        for row in table.rows:
            cells = [(cell.text or "").strip().replace("\n", " ") for cell in row.cells]
            joined = " | ".join(item for item in cells if item)
            if joined:
                lines.append(joined)

    return TextResult(text="\n".join(lines), page_count=max(1, len(lines) // 40 + 1), warnings=warnings)
