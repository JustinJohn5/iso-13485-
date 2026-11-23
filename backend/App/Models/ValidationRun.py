"""校验任务模型。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from App.Db.Base import Base
from App.Utils.TimeUtils import now

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"


class ValidationRun(Base):
    """一次合规校验任务的汇总结果。"""

    __tablename__ = "validation_runs"
    __table_args__ = {"comment": "校验任务"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_uid: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, comment="对外任务标识")
    rule_set_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="规则包标识")
    rule_set_version: Mapped[str] = mapped_column(String(16), nullable=False, comment="规则包版本")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=STATUS_PENDING, index=True)
    score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True, comment="合规得分")
    verdict: Mapped[str] = mapped_column(String(32), nullable=False, default="", comment="结论")
    passed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    critical_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    major_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    minor_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="参与判定的规则数")
    use_llm: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否启用大模型复核")
    llm_status: Mapped[str] = mapped_column(String(16), nullable=False, default="disabled", comment="大模型状态")
    llm_summary: Mapped[str] = mapped_column(Text, nullable=False, default="", comment="大模型复核摘要")
    llm_model: Mapped[str] = mapped_column(String(128), nullable=False, default="", comment="使用的模型")
    llm_latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="大模型耗时毫秒")
    note: Mapped[str] = mapped_column(String(500), nullable=False, default="", comment="备注")
    review_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="本次文件集正式依据的冻结快照")
    error_message: Mapped[str] = mapped_column(String(1000), nullable=False, default="", comment="失败原因")
    created_by: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ValidationRun id={self.id} status={self.status}>"
