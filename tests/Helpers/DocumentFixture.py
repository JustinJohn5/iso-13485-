"""通过标准 DOCX 容器生成脱敏手册样本，仅供浏览器上传测试。"""
from io import BytesIO
import sys

from docx import Document

document = Document()
for line in (
    '示例医疗器械公司', '质量管理体系手册', '文件编号：QM-01', '版本：01',
    '编制：质量部门 审核：质量经理 批准：负责人', '2020年02月01日发布',
    '适用范围：本质量管理体系适用于医疗器械产品的设计与生产。',
):
    document.add_paragraph(line)
buffer = BytesIO()
document.save(buffer)
sys.stdout.buffer.write(buffer.getvalue())
