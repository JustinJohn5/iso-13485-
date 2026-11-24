"""按整套发布版本独立保存的手册档案。"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from App.Db.Base import Base
from App.Utils.TimeUtils import now


class ManualSuite(Base):
    __tablename__ = 'manual_suites'
    __table_args__ = (UniqueConstraint('created_by', 'identity', name='uq_suite_owner_identity'),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    suite_uid: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    identity: Mapped[str] = mapped_column(String(64), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    inspection: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now)
