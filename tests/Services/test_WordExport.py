"""参考手册版式、动态字段与源文档内容隔离回归。"""
from copy import deepcopy
from io import BytesIO
from zipfile import ZipFile

from docx import Document
from docx.oxml.ns import qn
import pytest

from App.Services.Authoring.TemplateLibrary import TEMPLATES, build_snapshot
from App.Services.Authoring.WordExport import export_word


def snapshot():
    return build_snapshot('finished-inspection', {
        'company': '示例医疗科技有限公司', 'project': '净化项目', 'product': '测试产品',
        'model': 'MODEL-A', 'number': 'WI-09', 'version': 'B/2', 'requirements': '按确认的技术要求检验。',
    })


def test_reference_page_geometry_and_cover_are_applied():
    source = snapshot()
    frozen = deepcopy(source)
    document = Document(BytesIO(export_word(source, 3)))
    section = document.sections[0]
    assert (section.page_width.twips, section.page_height.twips) == (11907, 16840)
    assert [getattr(section, key).twips for key in
            ('top_margin', 'bottom_margin', 'left_margin', 'right_margin')] == [720, 569, 720, 720]
    assert section.different_first_page_header_footer
    assert not section.first_page_header.tables
    text = '\n'.join(p.text for p in document.paragraphs)
    for value in source['parameters'].values():
        assert value in text
    for label in ('编制：待填写', '审核：待填写', '批准：待填写', '发布日期：待批准后填写',
                  '实施日期：待批准后填写', '不作为产品放行', '更改历史', '目录', '文件信息'):
        assert label in text
    assert source == frozen


def test_header_contains_dynamic_identity_and_live_page_fields():
    document = Document(BytesIO(export_word(snapshot(), 3)))
    header = document.sections[0].header
    assert len(header.tables) == 1
    table = header.tables[0]
    assert len(table.rows) == 4
    text = '\n'.join(c.text for r in table.rows for c in r.cells)
    for value in ('成品检验规程', 'WI-09', 'B/2', '修改次数', '待填', '待批准'):
        assert value in text
    assert table.rows[1].cells[5].text == '待填'
    instructions = header._element.xpath('.//w:instrText/text() | .//w:fldSimple/@w:instr')
    assert any(value.strip() == 'PAGE' for value in instructions)
    assert any(value.strip() == 'NUMPAGES' for value in instructions)
    assert document.settings.element.find(qn('w:updateFields')).get(qn('w:val')) == 'true'
    footer_text = '\n'.join(p.text for p in document.sections[0].footer.paragraphs)
    assert '草稿修订 3' in footer_text


def test_change_record_keeps_source_columns_without_inventing_approval():
    document = Document(BytesIO(export_word(snapshot(), 3)))
    assert len(document.tables) == 1
    table = document.tables[0]
    assert [c.text for c in table.rows[0].cells] == ['版本号', '文件更改号', '更改概要', '修改人', '批准人']
    assert len(table.rows) == 26
    assert table.rows[1].cells[0].text == 'B/2'
    assert table.rows[1].cells[1].text == '草稿 r3'
    assert '模板 1.0' in table.rows[1].cells[2].text
    assert table.rows[1].cells[4].text == '待批准'
    assert '当前导出快照' in table.rows[1].cells[2].text


def test_body_indents_and_line_height_do_not_expand_header_or_record_cells():
    document = Document(BytesIO(export_word(snapshot(), 3)))
    for table in [document.sections[0].header.tables[0], document.tables[0]]:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    assert paragraph.paragraph_format.first_line_indent == 0
                    assert paragraph.paragraph_format.line_spacing == 1
    version = next(p for p in document.paragraphs if p.text == '版本：B/2')
    assert not version._p.xpath('./w:pPr/w:ind/@w:firstLineChars')


@pytest.mark.parametrize('template_id', [row['id'] for row in TEMPLATES])
def test_contents_link_to_headings_and_body_uses_reference_typography(template_id):
    source = build_snapshot(template_id, snapshot()['parameters'])
    document = Document(BytesIO(export_word(source, 1)))
    normal = document.styles['Normal']
    assert normal.element.rPr.rFonts.get(qn('w:eastAsia')) == '宋体'
    assert normal.font.size.pt == 12
    assert normal.paragraph_format.line_spacing == 1.5
    headings = [p for p in document.paragraphs if p.style.name == 'Heading 1']
    assert [p.text for p in headings] == [f'{i}.0 {s["title"]}' for i, s in enumerate(source['sections'], 1)]
    bookmarks = document.element.xpath('//w:bookmarkStart/@w:name')
    assert all(f'Chapter{i}' in bookmarks for i in range(1, len(source['sections']) + 1))
    fields = document.element.xpath('//w:fldSimple/@w:instr')
    assert all(any(f'PAGEREF Chapter{i} ' in field for field in fields)
               for i in range(1, len(source['sections']) + 1))


def test_long_identity_is_complete_on_cover_without_overflowing_header_columns():
    source = snapshot()
    source['parameters'].update(number='编号' * 60, version='版本' * 60, company='组织' * 60)
    content = export_word(source, 2)
    document = Document(BytesIO(content))
    text = '\n'.join(p.text for p in document.paragraphs)
    for key in ('number', 'version', 'company'):
        assert source['parameters'][key] in text
    assert '详见封面' in document.sections[0].header.tables[0].rows[0].cells[3].text
    assert '见封面' == document.sections[0].header.tables[0].rows[1].cells[3].text
    with ZipFile(BytesIO(content)) as package:
        assert not any(name.startswith('customXml/') for name in package.namelist())
        all_xml = b'\n'.join(package.read(name) for name in package.namelist() if name.endswith('.xml'))
        for original in ('XXXX公司', '2020年02月01日', 'QM-01', '颁布令'):
            assert original.encode() not in all_xml


def test_literal_template_markers_in_user_parameters_are_preserved():
    source = snapshot()
    source['parameters'].update(company='某某{{title}}科技有限公司', number='QM-{{version}}')
    document = Document(BytesIO(export_word(source, 2)))
    text = '\n'.join(p.text for p in document.paragraphs)
    assert source['parameters']['company'] in text
    assert '文件编号：QM-{{version}}' in text
