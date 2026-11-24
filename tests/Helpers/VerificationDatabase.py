"""测试副本验证码验证与可控时间；只处理本次随机前缀的数据。"""
from pathlib import Path
from datetime import timedelta
import json
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from App.Db.Session import session_scope
from App.Models.AuditLog import AuditLog
from App.Models.EmailVerificationCode import EmailVerificationCode
from App.Models.User import User
from App.Utils.Security import verify_password
from App.Utils.TimeUtils import now

if os.environ.get("APP_ENV") != "test" or not (make_url(os.environ["DATABASE_URL"]).database or "").endswith("_codextest"):
    raise SystemExit("拒绝连接非测试数据库")
address, action, purpose, value = sys.argv[1:5]
if not address.lower().startswith(os.environ["E2E_REGISTRATION_PREFIX"] + "-") or not address.lower().endswith("@example.com"):
    raise SystemExit("只能操作本次测试邮箱")

with session_scope() as db:
    challenge = db.execute(select(EmailVerificationCode).where(
        EmailVerificationCode.email == address.lower(), EmailVerificationCode.purpose == purpose)).scalar_one_or_none()
    if action == "no-user":
        assert db.execute(select(func.count(User.id)).where(User.email == address.lower())).scalar_one() == 0
    elif action == "no-challenge":
        assert challenge is None
    elif action == "password":
        user = db.execute(select(User).where(User.email == address.lower())).scalar_one()
        assert verify_password(value, user.password_hash), "新密码未正确保存"
        assert user.token_version == 2, "旧令牌版本未失效"
        assert db.execute(select(func.count(AuditLog.id)).where(
            AuditLog.user_id == user.id, AuditLog.action == "user_password_change")).scalar_one() == 1
    elif action == "age":
        assert challenge is not None
        challenge.issued_at = now() - timedelta(seconds=61)
    elif action == "expire":
        assert challenge is not None
        challenge.expires_at = now() - timedelta(seconds=1)
    elif action == "state":
        assert challenge is not None
        assert len(challenge.code_digest) == 64 and challenge.code_digest != value
        print(json.dumps({"used": challenge.used_at is not None,
                          "attempts": challenge.attempt_count,
                          "expired": challenge.expires_at <= now(),
                          "send_count": challenge.send_count}))
    else:
        raise SystemExit("未知的测试数据操作")
