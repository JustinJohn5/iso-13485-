from pathlib import Path

import pytest

from App.Utils.Errors import ApiError
from App.Utils.FileGuard import ensure_inside, ensure_supported_extension, sanitize_filename


def test_sanitize_filename_removes_path_and_control_characters():
    assert sanitize_filename("../../QMS\n控制程序.docx") == "QMS控制程序.docx"


def test_unsupported_legacy_format_has_conversion_guidance():
    with pytest.raises(ApiError, match="另存为 .docx"):
        ensure_supported_extension("old.doc")


def test_ensure_inside_rejects_path_traversal(tmp_path: Path):
    outside = tmp_path.parent / "outside.txt"
    with pytest.raises(ApiError):
        ensure_inside(outside, tmp_path)
