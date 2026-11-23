"""大模型配置模型（API Key 加密存储，永不回显明文）。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from App.Db.Base import Base
from App.Utils.TimeUtils import now


class LlmConfig(Base):
    """网页管理的大模型配置，运行时唯一来源。"""

    __tablename__ = "llm_configs"
    __table_args__ = {"comment": "大模型配置"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, default="default", unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    base_url: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    model: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    api_key_cipher: Mapped[str] = mapped_column(String(512), nullable=False, default="", comment="Fernet 密文")
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    max_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=2000)
    temperature: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False, default=Decimal("0.20"))
    updated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now, onupdate=now)
