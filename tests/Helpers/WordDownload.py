"""从浏览器实际下载件核对参考版式及当前/历史快照身份。"""
from pathlib import Path
import sys

from docx import Document


path, model, revision = sys.argv[1:]
document = Document(Path(path))
text = '\n'.join(p.text for p in document.paragraphs)
assert '自动化测试组织' in text
assert '文件编号：WI-01' in text
assert model in text
assert ('MODEL-A' if model == 'MODEL-B' else 'MODEL-B') not in text
assert '更改历史' in text and '成品检验规程目录' in text
assert document.sections[0].page_width.twips == 11907
assert len(document.sections[0].header.tables) == 1
assert document.tables[0].rows[1].cells[1].text == f'草稿 r{revision}'
assert f'编写修订 / 模板版本：{revision} / 2.0' in text
if revision == '3':
    assert '已核对技术要求及引用文件清单' in text
else:
    assert '已核对技术要求及引用文件清单' not in text
