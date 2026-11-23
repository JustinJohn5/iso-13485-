"""仅供 E2E 断言使用：读取隔离测试库，核对实际持久化结果。"""
from pathlib import Path
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))

from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from App.Db.Session import session_scope
from App.Models.ValidationDocument import ValidationDocument
from App.Models.ValidationRun import ValidationRun
from App.Models.User import User
from App.Models.UploadedFile import UploadedFile
from App.Models.AuditLog import AuditLog

if os.environ.get('APP_ENV') != 'test' or not (make_url(os.environ['DATABASE_URL']).database or '').endswith('_codextest'):
    raise SystemExit('拒绝连接非测试数据库')

with session_scope() as db:
    if sys.argv[1] == '--review':
        run = db.execute(select(ValidationRun).where(ValidationRun.run_uid == sys.argv[2])).scalar_one()
        frozen = run.review_snapshot
        assert frozen and frozen['decision_history'], '未保存确认依据快照'
        assert frozen['version_groups'][0]['decision']['file_uid'] == sys.argv[3], '历史快照被后续确认覆盖'
        files = db.execute(select(UploadedFile).where(UploadedFile.file_uid.in_([sys.argv[3], sys.argv[4]]))).scalars().all()
        assert len(files) == 2, '确认版本时不应删除原件'
        rows = db.execute(select(ValidationDocument).where(ValidationDocument.run_id == run.id)).scalars().all()
        assert len(rows) == 1 and rows[0].file_id == next(file.id for file in files if file.file_uid == sys.argv[3]), '计分范围未使用正式版'
        audit = db.execute(select(AuditLog).where(AuditLog.target_id == frozen['review_uid'], AuditLog.action == 'review_confirm')).scalars().all()
        assert audit, '确认未留下审计记录'
        raise SystemExit(0)
    if sys.argv[1] == '--count':
        count = db.execute(select(func.count(ValidationRun.id)).join(User, User.id == ValidationRun.created_by)
                           .where(User.email == os.environ['E2E_EMAIL'])).scalar_one()
        sys.stdout.write(str(count))
        raise SystemExit(0)
    run = db.execute(select(ValidationRun).where(ValidationRun.run_uid == sys.argv[1])).scalar_one()
    rows = db.execute(select(ValidationDocument).where(ValidationDocument.run_id == run.id)).scalars().all()
    assert len(rows) == int(sys.argv[2]), '持久化文档数量与去重结果不一致'
    assert all(row.document_type == sys.argv[3] for row in rows), '持久化文档类型错误'
