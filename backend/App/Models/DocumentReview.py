"""文件集版本选择及冲突依据的审查快照。"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from App.Db.Base import Base
from App.Utils.TimeUtils import now


class DocumentReview(Base):
    __tablename__ = 'document_reviews'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_uid: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)
