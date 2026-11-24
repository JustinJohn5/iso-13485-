"""邮箱验证码来源 IP 的短期发送配额；数据库只保存 IP 的 HMAC 摘要。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from App.Db.Base import Base
from App.Utils.TimeUtils import now


class EmailVerificationIpLimit(Base):
    __tablename__ = "email_verification_ip_limits"
    __table_args__ = (
        Index("ix_email_verification_ip_window", "window_started_at"),
        Index("ix_email_verification_ip_last_request", "last_requested_at"),
        {"comment": "邮箱验证码来源 IP 限流状态（IP 使用 HMAC 摘要）"},
    )

    ip_digest: Mapped[str] = mapped_column(String(64), primary_key=True, comment="来源 IP 的 HMAC-SHA256")
    window_started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now)
    last_requested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
