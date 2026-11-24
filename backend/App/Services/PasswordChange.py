"""当前密码与邮箱验证码均通过后修改密码，撤销既有登录令牌。"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from App.Dao.AuditLogDao import AuditLogDao
from App.Dao.UserDao import UserDao
from App.Models.User import User
from App.Schemas.PasswordChange import PasswordChangeRequest
from App.Services.EmailVerification import PASSWORD_CHANGE, consume_verification_code
from App.Utils.Errors import ApiError
from App.Utils.Security import hash_password, verify_password


def change_password(db: Session, user: User, payload: PasswordChangeRequest, ip_address: str) -> None:
    authenticated_version = user.token_version
    # 锁定并重新读取账号，避免并发改密使用过期密码与令牌版本。
    current = db.execute(select(User).where(User.id == user.id).with_for_update()
                         .execution_options(populate_existing=True)).scalar_one()
    if current.token_version != authenticated_version:
        raise ApiError(1103)
    if not verify_password(payload.current_password.get_secret_value(), current.password_hash):
        raise ApiError(1112)
    password = payload.password.get_secret_value()
    if verify_password(password, current.password_hash):
        raise ApiError(1105, "新密码不能与当前密码相同")
    consume_verification_code(db, current.email, PASSWORD_CHANGE, payload.email_verification_code)
    UserDao.update_password(db, current, hash_password(password))
    AuditLogDao.add(db, user_id=current.id, action="user_password_change", target_type="user",
                    target_id=str(current.id), detail="账号密码修改成功", ip_address=ip_address)
    db.commit()
