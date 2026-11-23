"""校验发现（不符合项/观察项）模型。"""

from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from App.Db.Base import Base

STATUS_PASS = "pass"
STATUS_FAIL = "fail"
STATUS_SKIPPED = "skipped"

SOURCE_RULE = "rule"
SOURCE_LLM = "llm"


class Finding(Base):
    """单条规则或大模型复核产出的发现记录。"""

    __tablename__ = "findings"
    __table_args__ = {"comment": "校验发现"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    rule_id: Mapped[str] = mapped_column(String(48), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    clause: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    clause_title: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="minor")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=STATUS_FAIL)
    document_type: Mapped[str] = mapped_column(String(48), nullable=False, default="")
    evidence: Mapped[str] = mapped_column(Text, nullable=False, default="")
    suggestion: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source: Mapped[str] = mapped_column(String(16), nullable=False, default=SOURCE_RULE)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
