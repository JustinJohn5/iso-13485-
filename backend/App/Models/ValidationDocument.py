"""校验任务与文档的关联模型。"""

from __future__ import annotations

from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from App.Db.Base import Base


class ValidationDocument(Base):
    """记录每次校验任务纳入了哪些文档及其判定类型。"""

    __tablename__ = "validation_documents"
    __table_args__ = {"comment": "校验任务文档明细"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    file_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(String(48), nullable=False, comment="文档类型标识")
    char_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
