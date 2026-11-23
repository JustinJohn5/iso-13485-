"""认证与密码安全工具。"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

import bcrypt
import jwt

from App.Config.Settings import get_settings
from App.Utils.Errors import ApiError
from App.Utils.TimeUtils import now_with_tz

JWT_ALGORITHM = "HS256"
_MAX_PASSWORD_BYTES = 72  # bcrypt 的硬限制
_PASSWORD_PATTERN = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,72}$")


def hash_password(password: str) -> str:
    """使用 bcrypt 生成密码哈希（禁止 MD5/SHA1）。"""
    raw = password.encode("utf-8")[:_MAX_PASSWORD_BYTES]
    return bcrypt.hashpw(raw, bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """校验密码；哈希损坏时返回 False 而不是抛异常。"""
    try:
        raw = password.encode("utf-8")[:_MAX_PASSWORD_BYTES]
        return bcrypt.checkpw(raw, password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def validate_password_policy(password: str) -> None:
    """密码策略：8~72 位，至少包含字母与数字。"""
    if not _PASSWORD_PATTERN.match(password):
        raise ApiError(1105, "密码需为 8~72 位，且同时包含字母与数字")


def create_access_token(user_id: int, token_version: int, role: str) -> tuple[str, int]:
    """签发访问令牌，返回 (token, 有效期秒数)。"""
    settings = get_settings()
    issued_at = now_with_tz()
    expires_at = issued_at + timedelta(minutes=settings.jwt_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "ver": token_version,
        "role": role,
        "typ": "access",
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)
    return token, settings.access_token_ttl_seconds


def decode_access_token(token: str) -> dict[str, Any]:
    """解析访问令牌；过期、被篡改、类型不符统一抛 1103。"""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise ApiError(1103, "登录已过期，请重新登录") from exc
    except jwt.InvalidTokenError as exc:
        raise ApiError(1103, "登录凭证无效，请重新登录") from exc
    if payload.get("typ") != "access":
        raise ApiError(1103, "登录凭证类型不正确")
    return payload
