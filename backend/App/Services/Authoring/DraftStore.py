"""草稿权限与乐观锁更新，正文仅存储于当前用户可访问的 MySQL 记录。"""
from copy import deepcopy

from sqlalchemy import select, update

from App.Dao.AuditLogDao import AuditLogDao
from App.Models.DocumentDraft import DocumentDraft
from App.Utils.Errors import ApiError
from App.Utils.TimeUtils import now


def accessible_draft(db, user, uid):
    row = db.execute(select(DocumentDraft).where(DocumentDraft.draft_uid == uid)).scalar_one_or_none()
    if row is None:
        raise ApiError(1702)
    if row.created_by != user.id and user.role != 'admin':
        raise ApiError(1104)
    return row


def history_entry(revision, snapshot, user_id, reason):
    return {'revision': revision, 'snapshot': deepcopy(snapshot), 'user_id': user_id,
            'reason': reason, 'created_at': now().isoformat()}


def draft_response(row):
    return {'draft_uid': row.draft_uid, 'revision': row.revision, 'snapshot': row.snapshot,
            'history': [{key: value for key, value in entry.items() if key != 'snapshot'} for entry in row.history]}


def save_revision(db, row, revision, snapshot, user, reason):
    if row.revision != revision:
        raise ApiError(1703)
    if len(row.history) >= 50:
        raise ApiError(1001, '草稿已达50次修订，请新建草稿以控制历史体积')
    history = row.history + [history_entry(revision + 1, snapshot, user.id, reason)]
    result = db.execute(update(DocumentDraft).where(DocumentDraft.id == row.id, DocumentDraft.revision == revision)
                        .values(revision=revision + 1, snapshot=snapshot, history=history)
                        .execution_options(synchronize_session=False))
    if result.rowcount != 1:
        db.rollback()
        raise ApiError(1703)
    AuditLogDao.add(db, user_id=user.id, action='draft_update', target_type='document_draft',
                    target_id=row.draft_uid, detail=f'revision={revision + 1};origin={snapshot["origin"]}')
    db.commit()
    db.refresh(row)
    return draft_response(row)
