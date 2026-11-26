"""管理员只读概览、访客状态、服务日志和操作记录。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from App.Api.Dependencies import require_admin
from App.Config.Settings import get_settings
from App.Db.Session import get_db
from App.Models.AuditLog import AuditLog
from App.Models.User import User
from App.Services.AdminLogs import read_logs, redact, safe_audit_detail
from App.Services.VisitorTracking import overview, visitors
from App.Utils.Pagination import page_payload, parse_page
from App.Utils.Response import success
from App.Utils.TimeUtils import to_iso

router = APIRouter(prefix='/api/v1/admin', tags=['后台管理'], dependencies=[Depends(require_admin)])


@router.get('/overview')
def get_overview(db: Session = Depends(get_db)):
    try:
        db.execute(text('SELECT 1'))
        available = True
    except SQLAlchemyError:
        db.rollback()
        available = False
    data = overview(db) if available else dict(online_visitors=0, online_users=0, today_visitors=0,
                                              today_views=0, timezone='Asia/Shanghai')
    data['services'] = {'api': 'ok', 'database': 'ok' if available else 'error'}
    return success(data)


@router.get('/visitors')
def get_visitors(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                 db: Session = Depends(get_db)):
    return success(visitors(db, page=page, page_size=page_size))


@router.get('/logs')
def get_logs(source: str = 'app', level: str = '', keyword: str = Query('', max_length=200),
             request_id: str = Query('', max_length=128), date: str = Query('', max_length=10)):
    return success(read_logs(get_settings().log_dir, source=source, level=level, keyword=keyword,
                             request_id=request_id, date=date))


@router.get('/audit-logs')
def get_audit_logs(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                   db: Session = Depends(get_db)):
    params = parse_page(page, page_size)
    total = int(db.execute(select(func.count(AuditLog.id))).scalar_one())
    rows = db.execute(select(AuditLog, User.display_name).outerjoin(User, AuditLog.user_id == User.id)
                      .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
                      .offset(params.offset).limit(params.page_size)).all()
    items = [{'id': log.id, 'actor': redact(name or ('系统' if log.user_id is None else f'用户#{log.user_id}')),
              'action': redact(log.action), 'target_type': redact(log.target_type),
              'target_id': redact(log.target_id), 'detail': safe_audit_detail(log.action, log.detail),
              'created_at': to_iso(log.created_at)}
             for log, name in rows]
    return success(page_payload(items, total, params))
