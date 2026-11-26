"""个人上传文件库、分组及原件下载接口。"""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from App.Api.Dependencies import current_user
from App.Config.Settings import get_settings
from App.Dao.AuditLogDao import AuditLogDao
from App.Db.Session import get_db
from App.Models.User import User
from App.Schemas.PersonalFiles import GroupMembers, GroupName
from App.Services import PersonalFiles as service
from App.Utils.FileGuard import sanitize_filename
from App.Utils.Response import success

router = APIRouter(prefix='/api/v1/my', tags=['个人文件'])


@router.get('/files')
def files(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
          keyword: str = Query('', max_length=255), document_type: str = Query('', max_length=48),
          group_uid: str = Query('', max_length=36), db: Session = Depends(get_db), user: User = Depends(current_user)):
    return success(service.list_files(db, user, page=page, page_size=page_size, keyword=keyword,
                                      document_type=document_type, group_uid=group_uid))


# 固定路径必须先注册，避免 selection 被动态文件标识吞掉。
@router.get('/files/selection')
def selection(file_uids: list[str] = Query(..., min_length=1, max_length=20),
              db: Session = Depends(get_db), user: User = Depends(current_user)):
    return success(service.selection_files(db, user, file_uids))


@router.get('/files/{uid}/download')
def download(uid: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    row, path = service.download_file(db, user, uid, get_settings().upload_dir)
    AuditLogDao.add(db, user_id=user.id, action='personal_file_download', target_type='file', target_id=uid)
    db.commit()
    return FileResponse(path, media_type=row.mime_type, filename=sanitize_filename(row.original_name),
                        headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})


@router.get('/file-groups')
def groups(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
           db: Session = Depends(get_db), user: User = Depends(current_user)):
    return success(service.list_groups(db, user, page=page, page_size=page_size))


@router.post('/file-groups')
def create(payload: GroupName, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return success(service.create_group(db, user, payload.name), '文件分组已创建')


@router.patch('/file-groups/{uid}')
def rename(uid: str, payload: GroupName, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return success(service.rename_group(db, user, uid, payload.name), '文件分组已重命名')


@router.delete('/file-groups/{uid}')
def remove(uid: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    service.delete_group(db, user, uid)
    return success(None, '文件分组已删除，原件已保留')


@router.post('/file-groups/{uid}/members')
def add_members(uid: str, payload: GroupMembers, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return success(service.change_members(db, user, uid, payload.file_uids, add=True), '文件已加入分组')


@router.delete('/file-groups/{uid}/members')
def remove_members(uid: str, payload: GroupMembers, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return success(service.change_members(db, user, uid, payload.file_uids, add=False), '文件已移出分组')
