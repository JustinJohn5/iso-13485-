"""固定次数 SQL 的匿名访客追踪和后台统计。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import re
import secrets
from uuid import uuid4

from fastapi import Request
from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.orm import Session

from App.Config.Settings import get_settings
from App.Models.User import User
from App.Models.Visitor import Visitor, VisitorDaily
from App.Utils.Errors import ApiError, param_error
from App.Utils.Pagination import page_payload, parse_page
from App.Utils.Security import decode_access_token
from App.Utils.TimeUtils import LOCAL_TZ, now, to_iso

COOKIE_NAME = 'iso_visitor'
COOKIE_MAX_AGE = 365 * 24 * 60 * 60
ONLINE_WINDOW = timedelta(minutes=5)
ALLOWED_PAGES = frozenset({
    '/', '/login', '/register', '/password', '/prescreen', '/history', '/manuals', '/authoring',
    '/rules', '/my/files', '/my/file-groups', '/admin/', '/admin/overview', '/admin/visitors',
    '/admin/models', '/admin/logs', '/admin/audit-logs',
})


@dataclass(frozen=True)
class VisitorIdentity:
    user_id: int
    token_version: int
    expires_at: datetime


def validate_page(page: str) -> str:
    if len(page) > 80 or page not in ALLOWED_PAGES:
        raise param_error('访客页面仅允许已登记的功能路径，不能包含查询参数')
    return page


def issue_visitor_cookie() -> str:
    return secrets.token_urlsafe(32)


def valid_visitor_cookie(value: str | None) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r'[A-Za-z0-9_-]{43}', value))


def cookie_digest(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def optional_identity(request: Request, db: Session) -> VisitorIdentity | None:
    """忽略无效会话，避免公开追踪接口阻止匿名访问；身份始终查库核实。"""
    token = request.cookies.get(get_settings().access_token_cookie_name)
    authorization = request.headers.get('authorization', '')
    if authorization.lower().startswith('bearer '):
        token = authorization[7:].strip()
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        user_id = int(payload['sub'])
        expires = datetime.fromtimestamp(int(payload['exp']), LOCAL_TZ).replace(tzinfo=None)
        version = int(payload['ver'])
        if user_id <= 0 or expires <= now():
            return None
    except (ApiError, KeyError, ValueError, TypeError, OverflowError, OSError):
        return None
    user = db.execute(select(User.id).where(User.id == user_id, User.is_active.is_(True),
                                           User.token_version == version)).scalar_one_or_none()
    return VisitorIdentity(user_id, version, expires) if user else None


def clear_visitor_identity(request: Request, db: Session) -> None:
    """供真实登出接口调用，与认证Cookie删除同一事务提交。"""
    cookie = request.cookies.get(COOKIE_NAME)
    if valid_visitor_cookie(cookie):
        db.execute(update(Visitor).where(Visitor.cookie_hash == cookie_digest(cookie)).values(
            user_id=None, token_version=None, token_expires_at=None))


def track_visit(db: Session, cookie: str, *, page: str, event: str,
                identity: VisitorIdentity | None = None, at: datetime | None = None) -> None:
    """两次原子 upsert 加一次查ID；并发心跳/浏览不会丢失每日PV。"""
    validate_page(page)
    if event not in {'pageview', 'heartbeat', 'logout'}:
        raise param_error('访客事件不正确')
    if not valid_visitor_cookie(cookie):
        raise param_error('访客凭据格式不正确')
    current = at or now()
    if event == 'logout' or (identity and identity.expires_at <= current):
        identity = None
    values = dict(user_id=identity.user_id if identity else None,
                  token_version=identity.token_version if identity else None,
                  token_expires_at=identity.expires_at if identity else None,
                  page=page, last_seen=current)
    statement = insert(Visitor).values(visitor_uid=str(uuid4()), cookie_hash=cookie_digest(cookie),
                                       first_seen=current, **values)
    db.execute(statement.on_duplicate_key_update(**values))
    visitor_id = db.execute(select(Visitor.id).where(Visitor.cookie_hash == cookie_digest(cookie))).scalar_one()
    if event == 'pageview':
        daily = insert(VisitorDaily).values(visitor_id=visitor_id, visit_date=current.date(), pageviews=1)
        db.execute(daily.on_duplicate_key_update(pageviews=VisitorDaily.pageviews + 1))
    db.commit()
    if event == 'pageview' and secrets.randbelow(100) == 0:
        cleanup_old_data(db, at=current)


def cleanup_old_data(db: Session, *, at: datetime | None = None,
                      visitor_limit: int = 5000, daily_limit: int = 10000) -> dict[str, int]:
    """清理超期数据；以有序ID批次删除，不遍历 ORM 行。"""
    if not 1 <= visitor_limit <= 5000 or not 1 <= daily_limit <= 10000:
        raise param_error('访客数据清理批次超出允许范围')
    current = at or now()
    daily_ids = db.execute(select(VisitorDaily.id).where(
        VisitorDaily.visit_date < current.date() - timedelta(days=400)
    ).order_by(VisitorDaily.id).limit(daily_limit)).scalars().all()
    visitor_ids = db.execute(select(Visitor.id).where(
        Visitor.last_seen < current - timedelta(days=90)
    ).order_by(Visitor.id).limit(visitor_limit)).scalars().all()
    daily_deleted = db.execute(delete(VisitorDaily).where(VisitorDaily.id.in_(daily_ids))).rowcount if daily_ids else 0
    visitors_deleted = db.execute(delete(Visitor).where(Visitor.id.in_(visitor_ids))).rowcount if visitor_ids else 0
    db.commit()
    return {'visitors': max(0, visitors_deleted or 0), 'daily': max(0, daily_deleted or 0)}


def _identity_join(current: datetime):
    return and_(Visitor.user_id == User.id, User.is_active.is_(True),
                Visitor.token_version == User.token_version, Visitor.token_expires_at > current)


def overview(db: Session, *, at: datetime | None = None) -> dict:
    current = at or now()
    online = db.execute(select(func.count(Visitor.id), func.count(func.distinct(User.id)))
                        .select_from(Visitor).outerjoin(User, _identity_join(current))
                        .where(Visitor.last_seen >= current - ONLINE_WINDOW)).one()
    daily = db.execute(select(func.count(VisitorDaily.id), func.coalesce(func.sum(VisitorDaily.pageviews), 0))
                       .where(VisitorDaily.visit_date == current.date())).one()
    return {'online_visitors': int(online[0]), 'online_users': int(online[1]),
            'today_visitors': int(daily[0]), 'today_views': int(daily[1]), 'timezone': 'Asia/Shanghai'}


def visitors(db: Session, *, page: int = 1, page_size: int = 20, at: datetime | None = None) -> dict:
    current = at or now()
    params = parse_page(page, page_size)
    total = db.execute(select(func.count(Visitor.id))).scalar_one()
    rows = db.execute(select(Visitor, User.id.label('active_user_id')).outerjoin(User, _identity_join(current))
                      .order_by(Visitor.last_seen.desc(), Visitor.id.desc())
                      .offset(params.offset).limit(params.page_size)).all()
    return page_payload([{
        'visitor_uid': visitor.visitor_uid, 'identity': 'user' if user_id else 'anonymous',
        'user_id': user_id, 'page': visitor.page, 'first_seen': to_iso(visitor.first_seen),
        'last_seen': to_iso(visitor.last_seen), 'online': visitor.last_seen >= current - ONLINE_WINDOW,
    } for visitor, user_id in rows], int(total), params)
