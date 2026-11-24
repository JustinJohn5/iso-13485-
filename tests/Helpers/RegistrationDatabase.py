"""仅从测试副本核对注册记录、密码哈希和审计，不输出凭证。"""
from pathlib import Path
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))

from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from App.Db.Session import session_scope
from App.Models.AuditLog import AuditLog
from App.Models.User import User
from App.Utils.Security import verify_password

if os.environ.get('APP_ENV') != 'test' or not (make_url(os.environ['DATABASE_URL']).database or '').endswith('_codextest'):
    raise SystemExit('拒绝连接非测试数据库')

address, expected = sys.argv[1].lower(), int(sys.argv[2])
if not address.startswith(os.environ['E2E_REGISTRATION_PREFIX'] + '-'):
    raise SystemExit('只能核对本次测试注册的账号')

with session_scope() as db:
    users = db.execute(select(User).where(User.email == address)).scalars().all()
    assert len(users) == expected, '注册记录数量不正确'
    if users:
        user = users[0]
        assert user.is_active and user.role == 'auditor', '新用户权限或状态不正确'
        assert user.display_name == '注册测试用户', '重复注册改写了原账号'
        assert user.password_hash != 'RegisterPass2026' and verify_password('RegisterPass2026', user.password_hash), '密码未正确哈希'
        count = db.execute(select(func.count(AuditLog.id)).where(AuditLog.action == 'user_register', AuditLog.user_id == user.id)).scalar_one()
        assert count == 1, '注册成功应仅有一条审计记录'
