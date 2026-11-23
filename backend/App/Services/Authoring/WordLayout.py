"""手册版式公共操作：沿用模板的段落属性，创建动态域及章节定位。"""
from copy import deepcopy

from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor, Twips


def set_text(paragraph, value):
    """保留参考件的首个字符样式及段落属性，替换可填写槽。"""
    properties = (deepcopy(paragraph.runs[0]._r.rPr)
                  if paragraph.runs and paragraph.runs[0]._r.rPr is not None else None)
    paragraph.clear()
    run = paragraph.add_run(value)
    if properties is not None:
        run._r.insert(0, properties)
    return run


def font(target, size, bold=False):
    target.font.name = 'Times New Roman'
    target.font.size = Pt(size)
    target.font.bold = bold
    target.font.color.rgb = RGBColor(0, 0, 0)
    target.element.get_or_add_rPr().get_or_add_rFonts().set(qn('w:eastAsia'), '宋体')


def configure_styles(document):
    normal = document.styles['Normal']
    font(normal, 12)
    normal.paragraph_format.line_spacing = 1.5
    normal.paragraph_format.space_after = Pt(0)
    normal.paragraph_format.keep_together = False
    normal.paragraph_format.keep_with_next = False
    normal.paragraph_format.widow_control = True
    normal.paragraph_format.first_line_indent = Pt(24)
    heading = document.styles['Heading 1']
    font(heading, 12, True)
    heading.paragraph_format.line_spacing = 1.5
    heading.paragraph_format.space_before = Pt(10)
    heading.paragraph_format.space_after = Pt(4)
    heading.paragraph_format.first_line_indent = Pt(0)
    heading.paragraph_format.keep_with_next = True
    heading.paragraph_format.keep_together = True


def compact_paragraph(paragraph):
    """表格和页眉页脚不继承正文的首行缩进与网格行距。"""
    format_ = paragraph.paragraph_format
    format_.first_line_indent = Pt(0)
    format_.left_indent = Pt(0)
    format_.right_indent = Pt(0)
    format_.line_spacing = 1
    format_.space_before = Pt(0)
    format_.space_after = Pt(0)
    format_.keep_with_next = False
    properties = paragraph._p.get_or_add_pPr()
    indent = properties.find(qn('w:ind'))
    if indent is not None:
        for name in ('firstLineChars', 'hangingChars', 'leftChars', 'rightChars'):
            indent.attrib.pop(qn('w:' + name), None)
    snap = properties.find(qn('w:snapToGrid'))
    if snap is None:
        snap = OxmlElement('w:snapToGrid')
        properties.append(snap)
    snap.set(qn('w:val'), 'false')


def configure_furniture(document):
    section = document.sections[0]
    for table in [*document.tables, *section.header.tables]:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    compact_paragraph(paragraph)
    for part in (section.header, section.footer):
        for paragraph in part.paragraphs:
            compact_paragraph(paragraph)


def narrow_cell_padding(cell):
    properties = cell._tc.get_or_add_tcPr()
    margins = OxmlElement('w:tcMar')
    for side in ('left', 'right'):
        element = OxmlElement('w:' + side)
        element.set(qn('w:w'), '20')
        element.set(qn('w:type'), 'dxa')
        margins.append(element)
    properties.append(margins)


def field(paragraph, instruction, cached='待更新'):
    element = OxmlElement('w:fldSimple')
    element.set(qn('w:instr'), instruction)
    run = OxmlElement('w:r')
    text = OxmlElement('w:t')
    text.text = cached
    run.append(text)
    element.append(run)
    paragraph._p.append(element)


def bookmark(paragraph, index):
    start, end = OxmlElement('w:bookmarkStart'), OxmlElement('w:bookmarkEnd')
    start.set(qn('w:id'), str(index))
    start.set(qn('w:name'), f'Chapter{index}')
    end.set(qn('w:id'), str(index))
    paragraph._p.insert(1 if paragraph._p.pPr is not None else 0, start)
    paragraph._p.append(end)


def front_heading(document, title):
    paragraph = document.add_paragraph(title)
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.first_line_indent = Pt(0)
    paragraph.paragraph_format.space_after = Pt(14)
    font(paragraph.runs[0], 16)
    return paragraph


def add_contents(document, snapshot, revision):
    front_heading(document, snapshot['title'] + '目录').paragraph_format.page_break_before = True
    section = document.sections[0]
    width = section.page_width.twips - section.left_margin.twips - section.right_margin.twips
    for index, item in enumerate(snapshot['sections'], 1):
        paragraph = document.add_paragraph(f'{index}.0 {item["title"]}\t')
        paragraph.paragraph_format.first_line_indent = Pt(0)
        paragraph.paragraph_format.left_indent = Pt(24)
        paragraph.paragraph_format.right_indent = Pt(24)
        paragraph.paragraph_format.tab_stops.add_tab_stop(Twips(width - 480), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
        field(paragraph, f'PAGEREF Chapter{index} \\h')
    heading = front_heading(document, '文件信息')
    heading.paragraph_format.space_before = Pt(24)
    for key, label in [('project', '项目'), ('product', '产品'), ('model', '型号')]:
        document.add_paragraph(f'{label}：{snapshot["parameters"][key]}')
    document.add_paragraph(f'编写修订 / 模板版本：{revision} / {snapshot["template_version"]}')
    document.add_paragraph('更改历史仅登记当前导出快照，完整编写修订可在网页查看。正式更改号、修改次数、人员及发放范围待确认。')


def enable_field_updates(document):
    settings = document.settings.element
    update = settings.find(qn('w:updateFields'))
    if update is None:
        update = OxmlElement('w:updateFields')
        settings.append(update)
    update.set(qn('w:val'), 'true')
