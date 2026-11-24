"""邮箱验证码状态；只保存用途绑定的 HMAC 摘要。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from App.Db.Base import Base
from App.Utils.TimeUtils import now


class EmailVerificationCode(Base):
    __tablename__ = "email_verification_codes"
    __table_args__ = (
        UniqueConstraint("email", "purpose", name="uq_email_verification_email_purpose"),
        Index("ix_email_verification_expires_at", "expires_at"),
        {"comment": "邮箱验证码状态"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(190), nullable=False, comment="规范化邮箱")
    purpose: Mapped[str] = mapped_column(String(32), nullable=False, comment="验证码用途")
    code_digest: Mapped[str] = mapped_column(String(64), nullable=False, comment="HMAC-SHA256")
    issued_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    send_window_started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    send_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
