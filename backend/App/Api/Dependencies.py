"""接口鉴权依赖。"""

from __future__ import annotations

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from App.Db.Session import get_db
from App.Config.Settings import get_settings
from App.Models.User import User
from App.Utils.Errors import ApiError
from App.Utils.Security import decode_access_token


def current_user(
    request: Request,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> User:
    """根据 Bearer 令牌或 HttpOnly Cookie 获取当前用户。"""
    token = request.cookies.get(get_settings().access_token_cookie_name)
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token:
        raise ApiError(1103)
    payload = decode_access_token(token)
    user = db.execute(select(User).where(User.id == int(payload["sub"]))).scalar_one_or_none()
    if user is None or not user.is_active or user.token_version != payload.get("ver"):
        raise ApiError(1103)
    return user


def require_writer(user: User) -> User:
    """只有管理员和审核员可以上传及发起校验。"""
    if user.role not in {"admin", "auditor"}:
        raise ApiError(1104)
    return user
