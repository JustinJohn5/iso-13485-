"""从已清理的手册版式副本导出草稿，不依赖用户本地参考件。"""
from io import BytesIO
from pathlib import Path

from docx import Document
from docx.shared import Pt

from App.Services.Authoring.WordLayout import (
    add_contents, bookmark, configure_furniture, configure_styles, enable_field_updates,
    field, font, narrow_cell_padding, set_text,
)

LAYOUT = Path(__file__).resolve().parents[2] / 'Assets' / 'Documents' / 'ManualLayout.docx'


def fill_cover(document, snapshot):
    values = {**snapshot['parameters'], 'title': snapshot['title']}
    for paragraph in document.paragraphs:
        for key in ('company', 'title', 'number', 'version'):
            marker = '{{' + key + '}}'
            if marker not in paragraph.text:
                continue
            run = set_text(paragraph, paragraph.text.replace(marker, values[key]))
            # 参考封面版本行带有字符单位缩进，替换为居中槽后应一并清除。
            for indent in paragraph._p.xpath('./w:pPr/w:ind'):
                for attribute in list(indent.attrib):
                    if attribute.endswith('Chars'):
                        del indent.attrib[attribute]
            if key == 'title':
                size = 62 if len(values[key]) <= 4 else 48 if len(values[key]) <= 6 else 36
                font(run, size, True)
            elif key == 'company':
                font(run, 26 if len(values[key]) <= 24 else 18, True)
            elif len(values[key]) > 32:
                font(run, 12, True)
            # 用户值中形如 {{title}} 的文本不再作为下一个模板槽解释。
            break
    # 长标识允许自然换行，压缩封面留白以保留签署栏，完整值始终保留。
    if any(len(values[key]) > 32 for key in ('company', 'number', 'version')):
        for paragraph in document.paragraphs:
            if paragraph.style.name == 'Title':
                paragraph.paragraph_format.space_before = Pt(60)
            elif paragraph.text == '编制：待填写':
                paragraph.paragraph_format.space_before = Pt(70)


def fill_header(document, snapshot, revision):
    section = document.sections[0]
    table = section.header.tables[0]
    values = [(0, 1, snapshot['title']), (0, 3, snapshot['parameters']['number']),
              (1, 3, snapshot['parameters']['version'])]
    for row, col, value in values:
        limit = 3 if row == 1 else 18
        placeholder = '见封面' if row == 1 else '详见封面'
        shown = placeholder if col == 3 and len(value) > limit else value
        cell = table.rows[row].cells[col]
        run = set_text(cell.paragraphs[0], shown)
        font(run, 16 if col == 1 else 8 if row == 1 else 11, col == 1)
        if row == 1:
            narrow_cell_padding(cell)
    changes = table.rows[1].cells[5]
    narrow_cell_padding(changes)
    font(set_text(changes.paragraphs[0], '待填'), 8.5)
    paragraph = table.rows[3].cells[3].paragraphs[0]
    set_text(paragraph, '第 ')
    field(paragraph, 'PAGE', '待更新')
    paragraph.add_run(' 页，共 ')
    field(paragraph, 'NUMPAGES', '待更新')
    paragraph.add_run(' 页')
    for run in paragraph.runs:
        font(run, 10)
    font(set_text(section.footer.paragraphs[0], f'草稿修订 {revision} · 模板 {snapshot["template_version"]}'), 9)


def fill_change_record(document, snapshot, revision):
    row = document.tables[0].rows[1]
    version = snapshot['parameters']['version']
    values = [version if len(version) <= 12 else '详见封面', f'草稿 r{revision}',
              f'当前导出快照；模板 {snapshot["template_version"]}；正式更改记录待填写', '待填写', '待批准']
    for cell, value in zip(row.cells, values):
        run = set_text(cell.paragraphs[0], value)
        font(run, 11)


def export_word(snapshot: dict, revision: int) -> bytes:
    document = Document(LAYOUT)
    configure_styles(document)
    configure_furniture(document)
    fill_cover(document, snapshot)
    fill_header(document, snapshot, revision)
    fill_change_record(document, snapshot, revision)
    add_contents(document, snapshot, revision)
    for index, item in enumerate(snapshot['sections'], 1):
        paragraph = document.add_heading(f'{index}.0 {item["title"]}', 1)
        if index == 1:
            paragraph.paragraph_format.page_break_before = True
        bookmark(paragraph, index)
        for line in item['body'].splitlines():
            document.add_paragraph(line)
    enable_field_updates(document)
    output = BytesIO()
    document.save(output)
    return output.getvalue()
