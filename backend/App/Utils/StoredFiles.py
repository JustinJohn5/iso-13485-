"""仅允许下载上传目录内的普通原件文件。"""
from pathlib import Path

from App.Utils.Errors import ApiError


def stored_file_path(stored_name: str, upload_dir: Path) -> Path:
    base = upload_dir.resolve()
    if not stored_name or '/' in stored_name or '\\' in stored_name:
        raise ApiError(1203)
    candidate = base / stored_name
    try:
        path = candidate.resolve(strict=True)
        valid = not candidate.is_symlink() and path.parent == base and path.is_file()
    except (OSError, RuntimeError):
        valid = False
    if not valid:
        raise ApiError(1203, '文件原件不存在或不可下载')
    return path
