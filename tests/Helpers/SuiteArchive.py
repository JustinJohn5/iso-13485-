"""浏览器下载包与测试数据库的实际保存结果交叉核对。"""
from io import BytesIO
import json
import os
from pathlib import Path
import sys
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))

from docx import Document
from sqlalchemy import select
from sqlalchemy.engine import make_url
from App.Db.Session import session_scope
from App.Models.AuditLog import AuditLog
from App.Models.ManualSuite import ManualSuite
from App.Models.User import User

if os.environ.get('APP_ENV') != 'test' or not (make_url(os.environ['DATABASE_URL']).database or '').endswith('_codextest'):
    raise SystemExit('拒绝连接非测试数据库')

with session_scope() as db:
    row = db.execute(select(ManualSuite).join(User, User.id == ManualSuite.created_by).where(
        ManualSuite.suite_uid == sys.argv[1], User.email == os.environ['E2E_EMAIL'])).scalar_one()
    assert row.version == 'A/0' and row.item_count == 21 and len(row.items) == 21
    current = row.inspection['current']
    assert current['rule_set']['version'] == '2.0.0'
    assert current['prescreen']['coverage']['denominator'] > 0
    assert '已核实范围' in row.items[0]['text']
    assert row.items[0]['file_version'] == 'B/1'
    assert row.items[-1]['file_version'] == 'B/2'
    audit = db.execute(select(AuditLog).where(AuditLog.target_id == row.suite_uid)).scalars().all()
    assert {'suite_create', 'suite_generate', 'suite_item_revise', 'suite_import', 'suite_inspect', 'suite_export'}.issubset({item.action for item in audit})
    assert any('按本次审核范围修订正文' in item.detail for item in audit)
    with ZipFile(sys.argv[2]) as archive:
        names = archive.namelist()
        assert len([name for name in names if name.endswith('.docx')]) == 20
        original = next(name for name in names if name.endswith('补充要求.txt'))
        assert 'EX-01' in archive.read(original).decode('utf-8')
        manifest = json.loads(archive.read('目录.json'))
        assert manifest['version'] == 'A/0' and len(manifest['items']) == 21
        assert json.loads(archive.read('检查结果.json')) == {**current, 'findings': current['prescreen']['items']}
        manual = next(name for name in names if name.endswith('质量手册.docx'))
        text = '\n'.join(p.text for p in Document(BytesIO(archive.read(manual))).paragraphs)
        assert '已核实范围' in text and 'MODEL-A' in text and 'B/1' in text
