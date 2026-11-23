"""统一 Word 排版；按草稿快照导出，保留待核实事项和修订标识。"""
from io import BytesIO

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


def export_word(snapshot: dict, revision: int) -> bytes:
    document = Document()
    section = document.sections[0]
    section.top_margin = section.bottom_margin = Cm(2)
    section.left_margin = section.right_margin = Cm(2.3)
    normal = document.styles['Normal']
    normal.font.name = 'Arial'
    normal.font.size = Pt(10.5)
    normal.element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'), '宋体')
    normal.paragraph_format.space_after = Pt(7)
    section.header.paragraphs[0].text = snapshot['parameters']['company'] + ' · 技术文件草稿'
    document.add_heading(snapshot['title'], 0)
    note = document.add_paragraph('草稿 · 待人工复核与批准；不作为产品放行或体系符合性依据。')
    note.runs[0].font.color.rgb = RGBColor.from_string('A34E28')
    table = document.add_table(rows=0, cols=2)
    table.style = 'Table Grid'
    labels = {'project': '项目', 'product': '产品', 'model': '型号', 'number': '文件编号', 'version': '文件版本'}
    for key, label in labels.items():
        cells = table.add_row().cells
        cells[0].text, cells[1].text = label, snapshot['parameters'][key]
    cells = table.add_row().cells
    cells[0].text, cells[1].text = '编写修订 / 模板版本', f"{revision} / {snapshot['template_version']}"
    for index, item in enumerate(snapshot['sections'], 1):
        document.add_heading(f"{index}. {item['title']}", 1)
        for line in item['body'].splitlines():
            document.add_paragraph(line)
    document.add_heading('人工确认与批准', 1)
    document.add_paragraph('编制：待填写    审核：待填写    批准：待填写    生效日期：待批准后填写')
    footer = section.footer.paragraphs[0]
    footer.add_run(f'草稿修订 {revision} · 第 ')
    field = OxmlElement('w:fldSimple')
    field.set(qn('w:instr'), 'PAGE')
    footer._p.append(field)
    footer.add_run(' 页')
    output = BytesIO()
    document.save(output)
    return output.getvalue()
