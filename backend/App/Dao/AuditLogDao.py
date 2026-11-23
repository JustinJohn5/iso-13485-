"""审计日志数据访问。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from App.Models.AuditLog import AuditLog


class AuditLogDao:
    """审计日志写入与查询。"""

    @staticmethod
    def add(
        db: Session,
        *,
        user_id: int | None,
        action: str,
        target_type: str = "",
        target_id: str = "",
        detail: str = "",
        ip_address: str = "",
    ) -> AuditLog:
        log = AuditLog(
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id)[:64],
            detail=detail[:500],
            ip_address=ip_address[:64],
        )
        db.add(log)
        return log

    @staticmethod
    def recent(db: Session, limit: int = 20) -> list[AuditLog]:
        return list(
            db.execute(
                select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit)
            ).scalars().all()
        )
