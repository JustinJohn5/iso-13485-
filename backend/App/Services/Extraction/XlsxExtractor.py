"""Excel（.xlsx）文本抽取：按工作表逐行拼接。"""

from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook

from App.Services.Extraction.TextResult import TextResult
from App.Utils.Errors import ApiError
from App.Utils.Logger import get_logger

logger = get_logger(__name__)

MAX_ROWS_PER_SHEET = 3000


def extract_xlsx(path: Path) -> TextResult:
    """抽取工作表名与单元格文本（只读模式，避免大文件占用内存）。"""
    try:
        workbook = load_workbook(filename=str(path), read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("XLSX 打开失败：%s", exc)
        raise ApiError(1204, "Excel 文件无法解析，可能已损坏") from exc

    warnings: list[str] = []
    lines: list[str] = []

    try:
        for sheet in workbook.worksheets:
            lines.append(f"工作表：{sheet.title}")
            row_count = 0
            for row in sheet.iter_rows(values_only=True):
                row_count += 1
                if row_count > MAX_ROWS_PER_SHEET:
                    warnings.append(f"工作表「{sheet.title}」超过 {MAX_ROWS_PER_SHEET} 行，仅判定前若干行")
                    break
                cells = [str(value).strip() for value in row if value is not None and str(value).strip()]
                if cells:
                    lines.append(" | ".join(cells))
    finally:
        workbook.close()

    return TextResult(text="\n".join(lines), page_count=len(workbook.sheetnames), warnings=warnings)
