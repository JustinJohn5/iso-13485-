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
from App.Schemas.Registration import RegistrationRequest
from App.Services.Registration import register_user
from App.Utils.Errors import ApiError
from App.Utils.Response import success
from App.Utils.Security import create_access_token, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["认证"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post('/register', status_code=201)
def register(payload: RegistrationRequest, request: Request, db: Session = Depends(get_db)):
    return success(register_user(db, payload, request.client.host if request.client else ''))


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


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(get_settings().access_token_cookie_name, path="/")
    return success(message="已退出登录")


@router.get("/me")
def me(user: User = Depends(current_user)):
    return success({"id": user.id, "email": user.email, "display_name": user.display_name, "role": user.role})
