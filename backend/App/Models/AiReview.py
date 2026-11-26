"""AI 文件审阅分析及人工决定历史。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from App.Db.Base import Base
from App.Utils.TimeUtils import now


class AiReview(Base):
    """独立保存一次 AI 候选分析，不参与规则评分。"""

    __tablename__ = "ai_reviews"
    __table_args__ = {"comment": "AI 文件审阅候选结果"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_uid: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("validation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(80), nullable=False)
    rule_title: Mapped[str] = mapped_column(String(255), nullable=False)
    clause: Mapped[str] = mapped_column(String(32), nullable=False)
    rule_set_version: Mapped[str] = mapped_column(String(16), nullable=False)
    file_uid: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    text_status: Mapped[str] = mapped_column(String(24), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    result: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now, index=True)


class AiReviewDecision(Base):
    """人工决定只追加，不覆盖原始 AI 分析或先前决定。"""

    __tablename__ = "ai_review_decisions"
    __table_args__ = {"comment": "AI 文件审阅人工决定历史"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ai_reviews.id", ondelete="CASCADE"), nullable=False, index=True
    )
    decided_by: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(24), nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    edited_result: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now, index=True)
