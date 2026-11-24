"""邮箱验证码：用途隔离、有效期、频率控制与单次使用。"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.orm import Session

from App.Config.Settings import get_settings
from App.Dao.UserDao import UserDao
from App.Models.EmailVerificationCode import EmailVerificationCode
from App.Models.EmailVerificationIpLimit import EmailVerificationIpLimit
from App.Services.EmailSender import EmailDeliveryError, send_verification_email
from App.Utils.ClientAddress import rate_limit_address
from App.Utils.Errors import ApiError
from App.Utils.Logger import get_logger
from App.Utils.TimeUtils import now

logger = get_logger(__name__)
REGISTRATION = "registration"
PASSWORD_CHANGE = "password_change"
CODE_TTL = timedelta(minutes=10)
RESEND_INTERVAL = timedelta(seconds=60)
SEND_WINDOW = timedelta(hours=1)
MAX_SENDS_PER_WINDOW = 5
IP_MAX_SENDS_PER_WINDOW = 20
MAX_ATTEMPTS = 5
IP_RATE_LIMIT_SCOPE = "email_verification_ip_v1"


def code_digest(email: str, purpose: str, code: str, secret: str) -> str:
    payload = f"iso13485-email-v1\0{purpose}\0{email.lower()}\0{code}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _ip_digest(address: str, secret: str) -> str:
    payload = f"{IP_RATE_LIMIT_SCOPE}\0{rate_limit_address(address)}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def request_verification_code(db: Session, email: str, purpose: str, client_ip: str = "unknown") -> dict:
    if purpose not in {REGISTRATION, PASSWORD_CHANGE}:
        raise ValueError("未知的邮箱验证码用途")
    settings = get_settings()
    if not settings.email_smtp_configured:
        raise ApiError(1110)
    address = email.strip().lower()

    issued = now()
    ip_digest = _ip_digest(client_ip, settings.jwt_secret)
    ip_statement = insert(EmailVerificationIpLimit).values(
        ip_digest=ip_digest, window_started_at=issued - SEND_WINDOW,
        last_requested_at=issued - SEND_WINDOW, request_count=0)
    db.execute(ip_statement.on_duplicate_key_update(ip_digest=EmailVerificationIpLimit.ip_digest))
    ip_limit = db.execute(select(EmailVerificationIpLimit).where(
        EmailVerificationIpLimit.ip_digest == ip_digest).with_for_update()).scalar_one()
    if issued - ip_limit.window_started_at >= SEND_WINDOW:
        ip_limit.window_started_at = issued
        ip_limit.request_count = 0
    if ip_limit.request_count >= IP_MAX_SENDS_PER_WINDOW:
        db.rollback()
        raise ApiError(1109)
    ip_limit.request_count += 1
    ip_limit.last_requested_at = issued
    db.execute(delete(EmailVerificationIpLimit).where(
        EmailVerificationIpLimit.last_requested_at < issued - timedelta(days=1)))
    db.commit()

    if purpose == REGISTRATION and UserDao.get_by_email(db, address) is not None:
        db.rollback()
        return {"expires_in_seconds": int(CODE_TTL.total_seconds()),
                "resend_after_seconds": int(RESEND_INTERVAL.total_seconds())}

    # MySQL 唯一键插入/锁定：同一邮箱首次并发请求也按同一行串行执行。
    statement = insert(EmailVerificationCode).values(
        email=address, purpose=purpose, code_digest="", issued_at=issued - RESEND_INTERVAL,
        expires_at=issued, send_window_started_at=issued, send_count=0, attempt_count=0)
    db.execute(statement.on_duplicate_key_update(id=EmailVerificationCode.id))
    challenge = db.execute(select(EmailVerificationCode).where(
        EmailVerificationCode.email == address, EmailVerificationCode.purpose == purpose
    ).with_for_update()).scalar_one()
    if issued - challenge.issued_at < RESEND_INTERVAL:
        db.rollback()
        raise ApiError(1109)
    if issued - challenge.send_window_started_at >= SEND_WINDOW:
        challenge.send_window_started_at = issued
        challenge.send_count = 0
    if challenge.send_count >= MAX_SENDS_PER_WINDOW:
        db.rollback()
        raise ApiError(1109)

    code = f"{secrets.randbelow(1_000_000):06d}"
    if hmac.compare_digest(challenge.code_digest, code_digest(address, purpose, code, settings.jwt_secret)):
        code = f"{(int(code) + 1) % 1_000_000:06d}"
    challenge.code_digest = code_digest(address, purpose, code, settings.jwt_secret)
    challenge.issued_at = issued
    challenge.expires_at = issued + CODE_TTL
    challenge.send_count += 1
    challenge.attempt_count = 0
    challenge.used_at = None
    # 持有行锁直到发信结束，避免重发和消费覆盖状态；SMTP 有严格超时且不自动重复发信。
    try:
        db.flush()
        send_verification_email(address, code)
        db.commit()
    except EmailDeliveryError:
        db.rollback()
        raise ApiError(1111) from None
    logger.info("验证码邮件已发送，用途=%s", purpose)
    return {"expires_in_seconds": int(CODE_TTL.total_seconds()),
            "resend_after_seconds": int(RESEND_INTERVAL.total_seconds())}


def consume_verification_code(db: Session, email: str, purpose: str, code: str) -> None:
    address = email.strip().lower()
    challenge = db.execute(select(EmailVerificationCode).where(
        EmailVerificationCode.email == address, EmailVerificationCode.purpose == purpose
    ).with_for_update()).scalar_one_or_none()
    current = now()
    if challenge is None or challenge.used_at is not None or challenge.expires_at <= current:
        raise ApiError(1108)
    expected = code_digest(address, purpose, code, get_settings().jwt_secret)
    if not hmac.compare_digest(challenge.code_digest, expected):
        challenge.attempt_count += 1
        if challenge.attempt_count >= MAX_ATTEMPTS:
            challenge.expires_at = current
        db.commit()
        raise ApiError(1108)
    challenge.used_at = current
