"""抽取器注册表：按扩展名分派，统一异常处理。"""

from __future__ import annotations

from pathlib import Path

from App.Services.Extraction.DocxExtractor import extract_docx
from App.Services.Extraction.PdfExtractor import extract_pdf
from App.Services.Extraction.PlainTextExtractor import extract_text_file
from App.Services.Extraction.TextResult import TextResult
from App.Services.Extraction.XlsxExtractor import extract_xlsx
from App.Utils.Errors import ApiError
from App.Utils.Logger import get_logger

logger = get_logger(__name__)

_EXTRACTORS = {
    ".pdf": extract_pdf,
    ".docx": extract_docx,
    ".xlsx": extract_xlsx,
    ".txt": extract_text_file,
    ".md": extract_text_file,
}


def extract(path: Path, extension: str) -> TextResult:
    """按扩展名抽取文本；未知类型直接拒绝。"""
    extractor = _EXTRACTORS.get(extension)
    if extractor is None:
        raise ApiError(1201, f"暂不支持抽取 {extension} 类型文件")
    try:
        result = extractor(path)
    except ApiError:
        raise
    except Exception as exc:  # noqa: BLE001 - 兜底为可读错误
        logger.exception("文件抽取出现未预期错误：%s", path.name)
        raise ApiError(1204, "文件解析失败，请确认文档未加密且格式正确") from exc
    logger.info("文件抽取完成：%s，字符数=%d，页数=%d", path.name, result.char_count, result.page_count)
    return result
