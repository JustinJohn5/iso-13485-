"""参数化文档草稿；各修订保存独立快照，不作为受控发布记录。"""
from sqlalchemy import Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from App.Db.Base import Base


class DocumentDraft(Base):
    __tablename__ = 'document_drafts'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    draft_uid: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    history: Mapped[list] = mapped_column(JSON, nullable=False)
