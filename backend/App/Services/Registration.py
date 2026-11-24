"""创建普通使用账号；依赖邮箱唯一索引保证并发注册不会重复。"""
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from App.Dao.AuditLogDao import AuditLogDao
from App.Dao.UserDao import UserDao
from App.Models.User import ROLE_AUDITOR
from App.Schemas.Registration import RegistrationRequest
from App.Utils.Errors import ApiError
from App.Utils.Logger import get_logger
from App.Utils.Security import hash_password

logger = get_logger(__name__)


def register_user(db: Session, payload: RegistrationRequest, ip_address: str) -> dict:
    try:
        user = UserDao.create(db, email=str(payload.email), display_name=payload.display_name,
                              password_hash=hash_password(payload.password.get_secret_value()), role=ROLE_AUDITOR)
        result = dict(id=user.id, email=user.email, display_name=user.display_name, role=user.role)
        AuditLogDao.add(db, user_id=user.id, action='user_register', target_type='user',
                        target_id=str(user.id), detail='普通使用账号注册成功', ip_address=ip_address)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if getattr(exc.orig, 'args', [None])[0] == 1062:
            logger.warning('注册拒绝：邮箱已注册')
            raise ApiError(1107) from exc
        raise
    except (OperationalError, ProgrammingError) as exc:
        db.rollback()
        if getattr(exc.orig, 'args', [None])[0] == 1146:
            raise ApiError(1501, '数据库业务表尚未初始化，请先按 README.md 完成初始化') from exc
        raise
    logger.info('账号注册成功，用户编号=%s', result['id'])
    return result
