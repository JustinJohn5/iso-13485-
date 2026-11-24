"""仅在 MySQL E2E 测试副本预置或清除验证码来源 IP 配额。"""
from __future__ import annotations

import hmac
import hashlib
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from sqlalchemy import delete, select
from sqlalchemy.engine import make_url

from App.Config.Settings import get_settings
from App.Db.Session import session_scope
from App.Models.EmailVerificationIpLimit import EmailVerificationIpLimit
from App.Services.EmailVerification import IP_MAX_SENDS_PER_WINDOW, IP_RATE_LIMIT_SCOPE
from App.Utils.TimeUtils import now

if os.environ.get("APP_ENV") != "test" or not (make_url(os.environ["DATABASE_URL"]).database or "").endswith("_codextest"):
    raise SystemExit("拒绝连接非测试数据库")
ip_address, action = sys.argv[1:3]
prefix = os.environ.get("E2E_REGISTRATION_PREFIX", "").removeprefix("reg-")
expected_ip = f"198.18.{int(prefix[:2], 16)}.{max(1, int(prefix[2:4], 16) % 254)}" if len(prefix) >= 4 else ""
if ip_address != expected_ip or action not in {"exhaust", "clear"}:
    raise SystemExit("仅允许操作本轮生成的测试来源 IP")

settings = get_settings()
key = hmac.new(settings.jwt_secret.encode(), f"{IP_RATE_LIMIT_SCOPE}\0{ip_address}".encode(), hashlib.sha256).hexdigest()
with session_scope() as db:
    row = db.execute(select(EmailVerificationIpLimit).where(
        EmailVerificationIpLimit.ip_digest == key)).scalar_one_or_none()
    if action == "clear":
        db.execute(delete(EmailVerificationIpLimit).where(EmailVerificationIpLimit.ip_digest == key))
    elif row is None:
        db.add(EmailVerificationIpLimit(ip_digest=key, window_started_at=now(),
                                        request_count=IP_MAX_SENDS_PER_WINDOW,
                                        last_requested_at=now()))
    else:
        row.window_started_at = now()
        row.request_count = IP_MAX_SENDS_PER_WINDOW
        row.last_requested_at = now()
