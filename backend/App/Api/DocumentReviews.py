"""文件集冲突审查：创建、恢复、确认；所有确认均留痕。"""
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from App.Api.Dependencies import current_user, require_writer
from App.Dao.AuditLogDao import AuditLogDao
from App.Dao.DocumentReviewDao import DocumentReviewDao
from App.Dao.FileDao import FileDao
from App.Db.Session import get_db
from App.Models.DocumentReview import DocumentReview
from App.Models.User import User
from App.Schemas.DocumentReview import ReviewCreate, ReviewDecision
from App.Services.DocumentControl.ReviewEngine import build_review, decide
from App.Services.DocumentControl.ReviewStore import accessible_review, review_response
from App.Utils.Errors import ApiError
from App.Utils.Logger import get_logger
from App.Utils.Response import success

router = APIRouter(prefix='/api/v1/document-reviews', tags=['文件集审查'])
logger = get_logger(__name__)


@router.post('')
def create_review(payload: ReviewCreate, db: Session = Depends(get_db), user: User = Depends(current_user)):
    require_writer(user)
    if len(set(payload.file_uids)) != len(payload.file_uids) or not set(payload.overrides).issubset(payload.file_uids):
        raise ApiError(1001, '文件不可重复，校正信息必须属于本次文件集')
    files = FileDao.get_by_uids(db, payload.file_uids)
    by_uid = {row.file_uid: row for row in files}
    if len(files) != len(payload.file_uids):
        raise ApiError(1203)
    if user.role != 'admin' and any(row.uploaded_by != user.id for row in files):
        raise ApiError(1104)
    snapshot = build_review([by_uid[uid] for uid in payload.file_uids], payload.as_of_date,
                            {uid: value.model_dump(exclude_unset=True) for uid, value in payload.overrides.items()})
    row = DocumentReview(review_uid=str(uuid4()), created_by=user.id, revision=1, snapshot=snapshot)
    db.add(row)
    AuditLogDao.add(db, user_id=user.id, action='review_create', target_type='document_review', target_id=row.review_uid)
    db.commit()
    logger.info('文件集审查已创建 user_id=%s review_uid=%s files=%s', user.id, row.review_uid, len(files))
    return success(review_response(row.review_uid, 1, snapshot))


@router.get('/{review_uid}')
def get_review(review_uid: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    row = accessible_review(db, user, review_uid)
    return success(review_response(row.review_uid, row.revision, row.snapshot))


@router.patch('/{review_uid}/decisions')
def confirm_decision(review_uid: str, payload: ReviewDecision, db: Session = Depends(get_db), user: User = Depends(current_user)):
    require_writer(user)
    row = accessible_review(db, user, review_uid)
    if row.revision != payload.revision:
        raise ApiError(1602)
    if len(row.snapshot['decision_history']) >= 500:
        raise ApiError(1001, '本次确认次数过多，请重新建立审查快照')
    snapshot = decide(row.snapshot, payload.kind, payload.issue_id, payload.file_uid, payload.reason, user.id)
    DocumentReviewDao.save_decision(db, review_uid, payload.revision, snapshot)
    AuditLogDao.add(db, user_id=user.id, action='review_confirm', target_type='document_review', target_id=review_uid,
                    detail=f'{payload.kind}:{payload.issue_id}:{payload.file_uid}')
    db.commit()
    logger.info('文件集依据已确认 user_id=%s review_uid=%s kind=%s', user.id, review_uid, payload.kind)
    return success(review_response(review_uid, payload.revision + 1, snapshot), '本次依据已确认并留痕')
