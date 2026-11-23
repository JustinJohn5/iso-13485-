"""跨草稿共享参数联动；先预览差异，再按同一版本提交。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from App.Api.Dependencies import current_user, require_writer
from App.Db.Session import get_db
from App.Models.User import User
from App.Schemas.DraftBatch import DraftBatchChange
from App.Services.Authoring.BatchUpdate import apply_batch, load_batch, preview
from App.Utils.Response import success

router = APIRouter(prefix='/api/v1/document-draft-batches', tags=['参数联动'])


@router.post('/preview')
def preview_batch(payload: DraftBatchChange, db: Session = Depends(get_db), user: User = Depends(current_user)):
    require_writer(user)
    return success(preview(load_batch(db, user, payload)))


@router.post('/apply')
def update_batch(payload: DraftBatchChange, db: Session = Depends(get_db), user: User = Depends(current_user)):
    require_writer(user)
    return success(apply_batch(db, user, payload), '参数已联动并保存各草稿新修订')
