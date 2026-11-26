"""匿名访客与按上海日期聚合的浏览计数；不存 IP 或原始 Cookie。"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from App.Db.Base import Base
from App.Utils.TimeUtils import now


class Visitor(Base):
    __tablename__ = 'visitors'
    __table_args__ = (Index('ix_visitors_last_seen_user', 'last_seen', 'user_id'),
                      {'comment': '匿名与登录访客当前状态，不保存原始凭据或IP'})

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    visitor_uid: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    cookie_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    token_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    page: Mapped[str] = mapped_column(String(80), nullable=False)
    first_seen: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now)
    last_seen: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now)


class VisitorDaily(Base):
    __tablename__ = 'visitor_daily'
    __table_args__ = (UniqueConstraint('visitor_id', 'visit_date', name='uq_visitor_daily_date'),
                      Index('ix_visitor_daily_date', 'visit_date'),
                      {'comment': 'Asia/Shanghai 每日唯一访客与浏览量，心跳不增加浏览量'})

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    visitor_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    visit_date: Mapped[date] = mapped_column(Date, nullable=False)
    pageviews: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
