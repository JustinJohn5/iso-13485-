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

if os.environ.get('APP_ENV') != 'test' or not (make_url(os.environ['DATABASE_URL']).database or '').endswith('_codextest'):
    raise SystemExit('拒绝连接非测试数据库')

with session_scope() as db:
    if sys.argv[1] == '--count':
        count = db.execute(select(func.count(ValidationRun.id)).join(User, User.id == ValidationRun.created_by)
                           .where(User.email == os.environ['E2E_EMAIL'])).scalar_one()
        sys.stdout.write(str(count))
        raise SystemExit(0)
    run = db.execute(select(ValidationRun).where(ValidationRun.run_uid == sys.argv[1])).scalar_one()
    rows = db.execute(select(ValidationDocument).where(ValidationDocument.run_id == run.id)).scalars().all()
    assert len(rows) == int(sys.argv[2]), '持久化文档数量与去重结果不一致'
    assert all(row.document_type == sys.argv[3] for row in rows), '持久化文档类型错误'
