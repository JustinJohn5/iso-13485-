"""检查浏览器实际下载的分组 ZIP，文件名安全且原件内容完整。"""
import json
from pathlib import PurePosixPath
import sys
from zipfile import ZipFile

expected = json.loads(sys.argv[2])
with ZipFile(sys.argv[1]) as archive:
    names = archive.namelist()
    assert len(names) == len(set(names)) == len(expected), '压缩包漏文件或重名覆盖'
    assert all(PurePosixPath(name).name == name and '\\' not in name for name in names), '压缩包含不安全路径'
    assert sorted(archive.read(name).decode('utf-8') for name in names) == sorted(expected), '原件内容发生变化'
