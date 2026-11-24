"""PDF 文本抽取（不依赖外部工具）。"""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from App.Services.Extraction.TextResult import TextResult
from App.Utils.Errors import ApiError
from App.Utils.Logger import get_logger

logger = get_logger(__name__)

MAX_PAGES = 300


def extract_pdf(path: Path) -> TextResult:
    """逐页抽取 PDF 文本；加密文件默认密码尝试失败即报错。"""
    try:
        reader = PdfReader(str(path))
    except Exception as exc:  # noqa: BLE001 - 统一转业务错误
        logger.warning("PDF 打开失败：%s", exc)
        raise ApiError(1204, "PDF 文件无法解析，可能已损坏") from exc

    if reader.is_encrypted:
        try:
            if reader.decrypt("") == 0:
                raise ApiError(1204, "PDF 已加密，无法抽取文本")
        except ApiError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("PDF 解密失败：%s", exc)
            raise ApiError(1204, "PDF 已加密，无法抽取文本") from exc

    warnings: list[str] = []
    pages = reader.pages
    total = len(pages)
    if total > MAX_PAGES:
        warnings.append(f"文档共 {total} 页，仅判定前 {MAX_PAGES} 页")

    chunks: list[str] = []
    for index, page in enumerate(pages[:MAX_PAGES]):
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # noqa: BLE001 - 单页失败不影响整体
            logger.warning("PDF 第 %d 页抽取失败：%s", index + 1, exc)
            warnings.append(f"第 {index + 1} 页文本抽取失败")
            text = ""
        if text.strip():
            chunks.append(text)
        elif not any(warning.startswith(f"第 {index + 1} 页") for warning in warnings):
            warnings.append(f"第 {index + 1} 页未抽取到文本，请核对空白页、扫描内容或图片")

    return TextResult(text="\n\n".join(chunks), page_count=total, warnings=warnings, incomplete=bool(warnings))
