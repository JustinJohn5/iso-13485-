"""审查快照数据访问，使用乐观锁防止覆盖其他确认。"""
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from App.Models.DocumentReview import DocumentReview
from App.Utils.Errors import ApiError


class DocumentReviewDao:
    @staticmethod
    def get(db: Session, uid: str) -> DocumentReview:
        row = db.execute(select(DocumentReview).where(DocumentReview.review_uid == uid)).scalar_one_or_none()
        if row is None:
            raise ApiError(1601)
        return row

    @staticmethod
    def save_decision(db: Session, uid: str, revision: int, snapshot: dict) -> None:
        result = db.execute(update(DocumentReview).where(DocumentReview.review_uid == uid, DocumentReview.revision == revision)
                            .values(snapshot=snapshot, revision=revision + 1).execution_options(synchronize_session=False))
        if result.rowcount != 1:
            raise ApiError(1602)
