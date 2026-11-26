"""AI 文件审阅数据访问。"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from App.Models.AiReview import AiReview, AiReviewDecision
from App.Models.UploadedFile import UploadedFile
from App.Models.ValidationDocument import ValidationDocument


class AiReviewDao:
    """AI 审阅记录和决定历史查询。"""

    @staticmethod
    def file_in_run(db: Session, run_id: int, file_uid: str) -> UploadedFile | None:
        return db.execute(
            select(UploadedFile)
            .join(ValidationDocument, ValidationDocument.file_id == UploadedFile.id)
            .where(ValidationDocument.run_id == run_id, UploadedFile.file_uid == file_uid)
        ).scalar_one_or_none()

    @staticmethod
    def count_for_run(db: Session, run_id: int) -> int:
        return int(db.execute(
            select(func.count(AiReview.id)).where(AiReview.run_id == run_id)
        ).scalar_one())

    @staticmethod
    def create(db: Session, row: AiReview) -> AiReview:
        db.add(row)
        db.flush()
        return row

    @staticmethod
    def get_by_uid(db: Session, review_uid: str) -> AiReview | None:
        return db.execute(
            select(AiReview).where(AiReview.review_uid == review_uid)
        ).scalar_one_or_none()

    @staticmethod
    def list_for_run(db: Session, run_id: int) -> list[AiReview]:
        return list(db.execute(
            select(AiReview)
            .where(AiReview.run_id == run_id)
            .order_by(AiReview.created_at.asc(), AiReview.id.asc())
        ).scalars().all())

    @staticmethod
    def list_decisions(db: Session, review_ids: list[int]) -> list[AiReviewDecision]:
        if not review_ids:
            return []
        return list(db.execute(
            select(AiReviewDecision)
            .where(AiReviewDecision.review_id.in_(review_ids))
            .order_by(AiReviewDecision.created_at.asc(), AiReviewDecision.id.asc())
        ).scalars().all())

    @staticmethod
    def add_decision(db: Session, row: AiReviewDecision) -> AiReviewDecision:
        db.add(row)
        db.flush()
        return row
