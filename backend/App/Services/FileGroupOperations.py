"""批量读取分组原件并构建完整 ZIP，临时文件由下载生命周期关闭。"""
from pathlib import Path
import re
from tempfile import TemporaryFile
from typing import BinaryIO
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy.orm import Session

from App.Models.User import User
from App.Services.PersonalFiles import group_files
from App.Utils.Errors import ApiError
from App.Utils.FileGuard import sanitize_filename
from App.Utils.StoredFiles import stored_file_path

MAX_ARCHIVE_FILES = 100
MAX_ARCHIVE_BYTES = 200 * 1024 * 1024
_CHUNK_SIZE = 1024 * 1024


def _safe_title(value: str) -> str:
    title = re.sub(r'[<>:"/\\|?*]', '-', sanitize_filename(value)).rstrip(' .') or '文件'
    suffix = Path(title).suffix[:16]
    return Path(title).stem[:64] + suffix


def build_group_archive(db: Session, user: User, uid: str, upload_dir: Path) -> tuple[str, BinaryIO]:
    group, files = group_files(db, user, uid, limit=MAX_ARCHIVE_FILES)
    paths = [stored_file_path(row.stored_name, upload_dir) for row in files]
    try:
        too_large = sum(path.stat().st_size for path in paths) > MAX_ARCHIVE_BYTES
    except OSError as exc:
        raise ApiError(1203, '部分原件不可读取，打包未完成') from exc
    if too_large:
        raise ApiError(1001, '分组原件合计超过200 MB，请拆分分组后下载')
    output = TemporaryFile(mode='w+b')
    total = 0
    try:
        with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
            for index, (row, path) in enumerate(zip(files, paths), 1):
                # 序号同时解决重名及 Windows 保留名，原始路径不进入压缩包。
                name = f'{index:03d}-{_safe_title(row.original_name)}'
                with path.open('rb') as source, archive.open(name, 'w') as target:
                    while chunk := source.read(_CHUNK_SIZE):
                        total += len(chunk)
                        if total > MAX_ARCHIVE_BYTES:
                            raise ApiError(1001, '分组原件合计超过200 MB，请拆分分组后下载')
                        target.write(chunk)
        output.seek(0)
        return _safe_title(group.name) + '.zip', output
    except Exception as exc:
        output.close()
        if isinstance(exc, OSError):
            raise ApiError(1203, '部分原件不可读取，打包未完成') from exc
        raise


def archive_chunks(output: BinaryIO):
    try:
        while chunk := output.read(_CHUNK_SIZE):
            yield chunk
    finally:
        output.close()
