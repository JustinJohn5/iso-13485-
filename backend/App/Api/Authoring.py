"""模板检索、草稿编写、历史恢复和 Word 导出。"""
from uuid import uuid4
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from App.Api.Dependencies import current_user, require_writer
from App.Dao.AuditLogDao import AuditLogDao
from App.Db.Session import get_db
from App.Models.DocumentDraft import DocumentDraft
from App.Models.User import User
from App.Schemas.DocumentDraft import DraftCreate, DraftUpdate
from App.Services.Authoring.DraftStore import accessible_draft, draft_response, history_entry, save_revision
from App.Services.Authoring.TemplateLibrary import build_snapshot, edit_sections, search_templates
from App.Services.Authoring.WordExport import export_word
from App.Utils.Errors import ApiError
from App.Utils.Response import success

router = APIRouter(prefix='/api/v1', tags=['文档编写'])


@router.get('/templates')
def templates(q: str = Query('', max_length=120), category: str = Query('', max_length=32),
              user: User = Depends(current_user)):
    return success(search_templates(q, category))


@router.get('/document-drafts')
def drafts(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.execute(select(DocumentDraft).where(DocumentDraft.created_by == user.id)
                      .order_by(DocumentDraft.id.desc()).limit(50)).scalars().all()
    return success([{'draft_uid': row.draft_uid, 'revision': row.revision, 'title': row.snapshot['title'],
                     'project': row.snapshot['parameters']['project']} for row in rows])


@router.post('/document-drafts')
def create(payload: DraftCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    require_writer(user)
    snapshot = build_snapshot(payload.template_id, payload.parameters)
    row = DocumentDraft(draft_uid=str(uuid4()), created_by=user.id, revision=1, snapshot=snapshot,
                        history=[history_entry(1, snapshot, user.id, '根据模板创建草稿')])
    db.add(row)
    AuditLogDao.add(db, user_id=user.id, action='draft_create', target_type='document_draft', target_id=row.draft_uid)
    db.commit()
    return success(draft_response(row))


@router.get('/document-drafts/{uid}')
def draft(uid: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return success(draft_response(accessible_draft(db, user, uid)))


@router.patch('/document-drafts/{uid}')
def revise(uid: str, payload: DraftUpdate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    require_writer(user)
    row = accessible_draft(db, user, uid)
    if (payload.parameters is None) == (payload.sections is None):
        raise ApiError(1001, '每次只允许更新参数或正文中的一项')
    snapshot = (build_snapshot(row.snapshot['template_id'], payload.parameters) if payload.parameters is not None
                else edit_sections(row.snapshot, payload.sections))
    return success(save_revision(db, row, payload.revision, snapshot, user, payload.reason))


@router.get('/document-drafts/{uid}/download')
def download(uid: str, revision: int | None = Query(None, ge=1),
             db: Session = Depends(get_db), user: User = Depends(current_user)):
    row = accessible_draft(db, user, uid)
    revision = revision or row.revision
    entry = next((entry for entry in row.history if entry['revision'] == revision), None)
    if entry is None:
        raise ApiError(1702, '草稿修订不存在')
    content = export_word(entry['snapshot'], revision)
    AuditLogDao.add(db, user_id=user.id, action='draft_export', target_type='document_draft',
                    target_id=uid, detail=f'revision={revision}')
    db.commit()
    filename = quote(f"{entry['snapshot']['title']}-草稿-r{revision}.docx")
    return Response(content, media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    headers={'Content-Disposition': f"attachment; filename*=UTF-8''{filename}", 'Cache-Control': 'no-store'})
