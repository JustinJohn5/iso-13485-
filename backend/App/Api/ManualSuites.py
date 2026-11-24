"""整套版本档案、批量生成与导入、统一检查和归档下载。"""
from hashlib import sha256
from urllib.parse import quote
from uuid import uuid4
import re

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from App.Api.Dependencies import current_user, require_writer
from App.Api.System import rule_loader
from App.Config.Settings import get_settings
from App.Dao.AuditLogDao import AuditLogDao
from App.Dao.FileDao import FileDao
from App.Dao.ManualSuiteDao import accessible_suite, save_suite, suite_response
from App.Db.Session import get_db
from App.Models.ManualSuite import ManualSuite
from App.Models.User import User
from App.Schemas.ManualSuite import (SuiteCreate, SuiteGenerate, SuiteImport, SuiteInspection,
                                     SuiteItemUpdate, SuiteMutation)
from App.Services.ManualSuites.Archive import build_archive
from App.Services.ManualSuites.Catalog import catalog
from App.Services.ManualSuites.Content import generate_items, import_items, revise_item
from App.Services.ManualSuites.Inspection import inspect_items
from App.Utils.Errors import ApiError
from App.Utils.Response import success
from App.Utils.TimeUtils import to_iso

router = APIRouter(prefix='/api/v1', tags=['整套手册'])


@router.get('/manual-suite-catalog')
def directory(user: User = Depends(current_user)):
    return success(catalog())


@router.get('/manual-suites')
def suites(q: str = Query('', max_length=120), version: str = Query('', max_length=32),
           page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
           db: Session = Depends(get_db), user: User = Depends(current_user)):
    filters = [ManualSuite.created_by == user.id]
    if q:
        filters.append(ManualSuite.name.contains(q, autoescape=True))
    if version:
        filters.append(ManualSuite.version == version)
    total = db.execute(select(func.count()).select_from(ManualSuite).where(*filters)).scalar_one()
    rows = db.execute(select(ManualSuite.suite_uid, ManualSuite.name, ManualSuite.version,
                             ManualSuite.revision, ManualSuite.item_count, ManualSuite.updated_at)
                      .where(*filters).order_by(ManualSuite.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return success(dict(total=total, page=page, page_size=page_size,
                        items=[{**row._asdict(), 'updated_at': to_iso(row.updated_at)} for row in rows]))


@router.post('/manual-suites')
def create(payload: SuiteCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    require_writer(user)
    identity = sha256((payload.name.casefold() + '\x00' + payload.version.casefold()).encode()).hexdigest()
    row = ManualSuite(suite_uid=str(uuid4()), created_by=user.id, name=payload.name, version=payload.version,
                      identity=identity, revision=1, item_count=0, items=[], inspection=None)
    db.add(row)
    AuditLogDao.add(db, user_id=user.id, action='suite_create', target_type='manual_suite', target_id=row.suite_uid)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if exc.orig.args[0] == 1062:
            raise ApiError(1803) from exc
        raise
    return success(suite_response(row))


@router.get('/manual-suites/{uid}')
def detail(uid: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return success(suite_response(accessible_suite(db, user, uid)))


@router.post('/manual-suites/{uid}/generations')
def generate(uid: str, payload: SuiteGenerate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    require_writer(user)
    row = accessible_suite(db, user, uid, payload.revision)
    items = generate_items(row.items, payload.catalog_keys, payload.parameters, row.version)
    return success(save_suite(db, user, row, payload.revision, items=items, action='suite_generate'))


@router.post('/manual-suites/{uid}/imports')
def import_files(uid: str, payload: SuiteImport, db: Session = Depends(get_db), user: User = Depends(current_user)):
    require_writer(user)
    row = accessible_suite(db, user, uid, payload.revision)
    if len(set(payload.file_uids)) != len(payload.file_uids):
        raise ApiError(1001, '请提交不重复的文件')
    # 固定一次批量查询，不随文件数量增加 SQL 往返。
    files = FileDao.get_by_uids(db, payload.file_uids)
    if len(files) != len(payload.file_uids):
        raise ApiError(1203)
    if user.role != 'admin' and any(file.uploaded_by != user.id for file in files):
        raise ApiError(1104)
    if any(file.text_status != 'ok' for file in files):
        raise ApiError(1204)
    by_uid = {file.file_uid: file for file in files}
    items = import_items(row.items, [by_uid[key] for key in payload.file_uids])
    return success(save_suite(db, user, row, payload.revision, items=items, action='suite_import'))


@router.get('/manual-suites/{uid}/items/{item_id}')
def read_item(uid: str, item_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    row = accessible_suite(db, user, uid)
    item = next((item for item in row.items if item['id'] == item_id), None)
    if item is None:
        raise ApiError(1801, '套册成员不存在')
    result = {key: value for key, value in item.items() if key not in {'stored_name', 'snapshot'}}
    if item['origin'] == 'generated':
        result['sections'] = item['snapshot']['sections']
    return success(result)


@router.patch('/manual-suites/{uid}/items/{item_id}')
def revise(uid: str, item_id: str, payload: SuiteItemUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    require_writer(user)
    row = accessible_suite(db, user, uid, payload.revision)
    if payload.sections is not None and len(payload.reason.strip()) < 5:
        raise ApiError(1001, '保存正文时请填写至少5字的变更原因')
    items = revise_item(row.items, item_id, payload.catalog_key, payload.file_version, sections=payload.sections)
    return success(save_suite(db, user, row, payload.revision, items=items, action='suite_item_revise', reason=payload.reason))


@router.delete('/manual-suites/{uid}/items/{item_id}')
def remove(uid: str, item_id: str, payload: SuiteMutation, db: Session = Depends(get_db), user: User = Depends(current_user)):
    require_writer(user)
    row = accessible_suite(db, user, uid, payload.revision)
    items = [item for item in row.items if item['id'] != item_id]
    if len(items) == len(row.items):
        raise ApiError(1801, '套册成员不存在')
    return success(save_suite(db, user, row, payload.revision, items=items, action='suite_item_remove'))


@router.post('/manual-suites/{uid}/inspections')
def inspect(uid: str, payload: SuiteInspection, db: Session = Depends(get_db), user: User = Depends(current_user)):
    require_writer(user)
    row = accessible_suite(db, user, uid, payload.revision)
    report = inspect_items(row.items, rule_loader().get(), payload.as_of_date.isoformat())
    return success(save_suite(db, user, row, payload.revision, inspection=report, action='suite_inspect'))


@router.get('/manual-suites/{uid}/download')
def download(uid: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    row = accessible_suite(db, user, uid)
    content = build_archive(row, get_settings().upload_dir)
    AuditLogDao.add(db, user_id=user.id, action='suite_export', target_type='manual_suite',
                    target_id=row.suite_uid, detail=f'revision={row.revision}')
    db.commit()
    filename = re.sub(r'[<>:"/\\|?*]', '-', f'{row.name}-{row.version}.zip')
    return Response(content, media_type='application/zip', headers={
        'Content-Disposition': f"attachment; filename*=UTF-8''{quote(filename)}", 'Cache-Control': 'no-store'})
