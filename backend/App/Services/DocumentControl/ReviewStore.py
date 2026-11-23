"""审查权限、输入快照一致性和校验文件范围。"""
from copy import deepcopy

from App.Dao.DocumentReviewDao import DocumentReviewDao
from App.Services.DocumentControl.ReviewEngine import build_review, review_ready
from App.Services.DocumentControl.Versions import selected_documents
from App.Utils.Errors import ApiError
from App.Utils.TimeUtils import now


def accessible_review(db, user, uid):
    row = DocumentReviewDao.get(db, uid)
    if user.role != 'admin' and row.created_by != user.id:
        raise ApiError(1104)
    return row


def check_snapshot_files(snapshot: dict, files: list) -> None:
    current = {row.file_uid: row for row in files}
    if set(current) != {row['file_uid'] for row in snapshot['documents']}:
        raise ApiError(1603)
    if any(current[row['file_uid']].sha256 != row['sha256'] or
           current[row['file_uid']].document_type != row['document_type'] for row in snapshot['documents']):
        raise ApiError(1603)


def validation_scope(db, user, files: list, uid: str, revision: int | None = None) -> tuple[list[str], dict | None]:
    if not uid:
        snapshot = build_review(files, now().date(), {})
        if not review_ready(snapshot):
            raise ApiError(1604)
        return [row.file_uid for row in files], None
    row = accessible_review(db, user, uid)
    if revision != row.revision:
        raise ApiError(1602)
    check_snapshot_files(row.snapshot, files)
    if not review_ready(row.snapshot):
        raise ApiError(1604)
    frozen = {'review_uid': uid, 'revision': row.revision, 'ready': True, **deepcopy(row.snapshot)}
    return [item['file_uid'] for item in selected_documents(row.snapshot)], frozen


def review_response(uid: str, revision: int, snapshot: dict) -> dict:
    return {'review_uid': uid, 'revision': revision, 'ready': review_ready(snapshot), **snapshot}
