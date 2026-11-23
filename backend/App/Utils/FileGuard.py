"""上传文件安全校验：扩展名白名单、魔数校验、文件名清洗、存储路径生成。"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from uuid import uuid4

from App.Utils.Errors import ApiError

# 允许的扩展名 -> 规范 MIME
ALLOWED_EXTENSIONS: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".txt": "text/plain",
    ".md": "text/markdown",
}

# 明确不支持但给出引导的老格式
LEGACY_EXTENSIONS: dict[str, str] = {
    ".doc": "请先用 Word 另存为 .docx 再上传",
    ".xls": "请先用 Excel 另存为 .xlsx 再上传",
    ".wps": "请先导出为 .docx 或 .pdf 再上传",
    ".et": "请先导出为 .xlsx 再上传",
}

OOXML_MARKERS: dict[str, str] = {
    ".docx": "word/document.xml",
    ".xlsx": "xl/workbook.xml",
}


def normalize_extension(filename: str) -> str:
    """取小写扩展名，缺失时返回空串。"""
    return Path(filename).suffix.lower()


def sanitize_filename(raw_name: str) -> str:
    """清洗上传文件名：去路径、去控制字符、限制长度。

    只用于展示与审计；落盘一律使用随机文件名，避免目录穿越与重名覆盖。
    """
    name = (raw_name or "").replace("\\", "/").split("/")[-1]
    name = unicodedata.normalize("NFKC", name)
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()
    name = name.replace("..", "_")
    if not name:
        return "上传文件"
    if len(name) <= 150:
        return name
    suffix = Path(name).suffix[:16]
    return name[: 150 - len(suffix)] + suffix


def ensure_supported_extension(filename: str) -> str:
    """扩展名白名单校验，老格式给出明确转换提示。"""
    ext = normalize_extension(filename)
    if ext in LEGACY_EXTENSIONS:
        raise ApiError(1201, f"暂不支持 {ext} 格式，{LEGACY_EXTENSIONS[ext]}")
    if ext not in ALLOWED_EXTENSIONS:
        allowed = "、".join(sorted(ALLOWED_EXTENSIONS))
        raise ApiError(1201, f"仅支持 {allowed} 格式的文档")
    return ext


def canonical_mime(extension: str) -> str:
    """规范 MIME，未知类型回落到二进制。"""
    return ALLOWED_EXTENSIONS.get(extension, "application/octet-stream")


def verify_signature(extension: str, head: bytes, path: Path) -> None:
    """用文件头（必要时加 zip 结构）验证扩展名与真实内容一致。"""
    if extension == ".pdf":
        if not head.startswith(b"%PDF"):
            raise ApiError(1206, "文件内容不是有效的 PDF")
        return

    if extension in OOXML_MARKERS:
        if not head.startswith(b"PK\x03\x04"):
            raise ApiError(1206, "文件内容不是有效的 Office 文档")
        _verify_ooxml(extension, path)
        return

    if extension in (".txt", ".md"):
        if b"\x00" in head[:2048]:
            raise ApiError(1206, "文本文件包含二进制内容")
        return


def _verify_ooxml(extension: str, path: Path) -> None:
    """校验 OOXML 压缩包内是否包含声明的部件。"""
    from zipfile import BadZipFile, ZipFile

    marker = OOXML_MARKERS[extension]
    try:
        with ZipFile(path) as archive:
            names = set(archive.namelist())
            if marker not in names:
                raise ApiError(1206, "Office 文档结构不完整，无法识别")
            uncompressed = sum(info.file_size for info in archive.infolist())
            if uncompressed > 300 * 1024 * 1024:
                raise ApiError(1206, "文档解压后体积过大，已拒绝处理")
    except BadZipFile as exc:
        raise ApiError(1206, "Office 文档已损坏") from exc


def build_storage_path(upload_dir: Path, extension: str) -> tuple[str, Path]:
    """生成随机落盘文件名，返回 (存储名, 绝对路径)。"""
    stored_name = f"{uuid4().hex}{extension}"
    return stored_name, (upload_dir / stored_name).resolve()


def ensure_inside(path: Path, base_dir: Path) -> Path:
    """防目录穿越：目标路径必须位于允许的根目录内。"""
    resolved = path.resolve()
    base = base_dir.resolve()
    if resolved != base and base not in resolved.parents:
        raise ApiError(1003, "非法的文件路径")
    return resolved
