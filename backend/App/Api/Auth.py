"""登录与当前账号接口。"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from App.Config.Settings import get_settings
from App.Api.Dependencies import current_user
from App.Db.Session import get_db
from App.Dao.UserDao import UserDao
from App.Models.User import User
from App.Schemas.Registration import RegistrationCodeRequest, RegistrationRequest
from App.Schemas.PasswordChange import PasswordChangeRequest
from App.Services.EmailVerification import PASSWORD_CHANGE, REGISTRATION, request_verification_code
from App.Services.PasswordChange import change_password
from App.Services.Registration import register_user
from App.Utils.Errors import ApiError
from App.Utils.ClientAddress import resolve_client_ip
from App.Utils.Response import success
from App.Utils.Security import create_access_token, decode_access_token, verify_password
from App.Dao.AuditLogDao import AuditLogDao
from App.Services.VisitorTracking import clear_visitor_identity
from App.Utils.TimeUtils import now

router = APIRouter(prefix="/api/v1/auth", tags=["认证"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def _client_ip(request: Request) -> str:
    settings = get_settings()
    return resolve_client_ip(
        request.client.host if request.client else None,
        request.headers.get("x-forwarded-for"),
        settings.trusted_proxy_cidrs.split(","),
    )


@router.post("/registration-codes")
def registration_code(payload: RegistrationCodeRequest, request: Request, db: Session = Depends(get_db)):
    return success(request_verification_code(db, str(payload.email), REGISTRATION, _client_ip(request)))


@router.post("/password-change-codes")
def password_change_code(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return success(request_verification_code(db, user.email, PASSWORD_CHANGE, _client_ip(request)))


@router.patch("/password")
def update_password(payload: PasswordChangeRequest, request: Request, response: Response,
                    user: User = Depends(current_user), db: Session = Depends(get_db)):
    change_password(db, user, payload, _client_ip(request))
    response.delete_cookie(get_settings().access_token_cookie_name, path="/")
    return success(message="密码已修改，请重新登录")


@router.post('/register', status_code=201)
def register(payload: RegistrationRequest, request: Request, db: Session = Depends(get_db)):
    return success(register_user(db, payload, _client_ip(request)))


@router.post("/login")
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    try:
        user = UserDao.get_by_email(db, str(payload.email).lower())
    except (OperationalError, ProgrammingError) as exc:
        if getattr(exc.orig, "args", [None])[0] == 1146:
            raise ApiError(1501, "数据库业务表尚未初始化，请先按 README.md 完成开发库初始化") from exc
        raise
    if user is None or not verify_password(payload.password, user.password_hash):
        raise ApiError(1101)
    if not user.is_active:
        raise ApiError(1106)
    user.last_login_at = now()
    AuditLogDao.add(db, user_id=user.id, action="user_login", target_type="user",
                    target_id=str(user.id), detail="账号登录成功", ip_address="")
    db.commit()
    token, ttl = create_access_token(user.id, user.token_version, user.role)
    settings = get_settings()
    response.set_cookie(
        settings.access_token_cookie_name,
        token,
        max_age=ttl,
        httponly=True,
        secure=settings.is_prod,
        samesite="lax",
        path="/",
    )
    return success({"id": user.id, "email": user.email, "display_name": user.display_name, "role": user.role})


def _logout_user(request: Request, db: Session) -> User | None:
    """仅把仍有效且未撤销的会话关联到退出审计事件。"""
    token = request.cookies.get(get_settings().access_token_cookie_name)
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        user = UserDao.get_by_id(db, int(payload["sub"]))
    except (ApiError, KeyError, TypeError, ValueError, OverflowError):
        return None
    if user is None or not user.is_active or user.token_version != payload.get("ver"):
        return None
    return user


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    user = _logout_user(request, db)
    clear_visitor_identity(request, db)
    if user:
        AuditLogDao.add(db, user_id=user.id, action="user_logout", target_type="user",
                        target_id=str(user.id), detail="账号退出登录成功", ip_address=_client_ip(request))
    db.commit()
    response.delete_cookie(get_settings().access_token_cookie_name, path="/")
    return success(message="已退出登录")


@router.get("/me")
def me(user: User = Depends(current_user)):
    return success({"id": user.id, "email": user.email, "display_name": user.display_name, "role": user.role})
