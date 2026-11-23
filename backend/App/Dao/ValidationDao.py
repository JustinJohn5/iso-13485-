"""校验任务与发现数据访问。"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from App.Models.Finding import Finding, SOURCE_RULE, STATUS_PASS
from App.Models.ValidationDocument import ValidationDocument
from App.Models.ValidationRun import ValidationRun


class ValidationDao:
    """校验任务相关表读写。"""

    # ---------- 任务 ----------
    @staticmethod
    def create_run(db: Session, run: ValidationRun) -> ValidationRun:
        db.add(run)
        db.flush()
        return run

    @staticmethod
    def get_by_uid(db: Session, run_uid: str) -> ValidationRun | None:
        return db.execute(
            select(ValidationRun).where(ValidationRun.run_uid == run_uid)
        ).scalar_one_or_none()

    @staticmethod
    def get_by_id(db: Session, run_id: int) -> ValidationRun | None:
        return db.get(ValidationRun, run_id)

    @staticmethod
    def list_paged(
        db: Session, *, offset: int, limit: int, status: str = ""
    ) -> tuple[list[ValidationRun], int]:
        stmt = select(ValidationRun)
        count_stmt = select(func.count(ValidationRun.id))
        if status:
            stmt = stmt.where(ValidationRun.status == status)
            count_stmt = count_stmt.where(ValidationRun.status == status)
        total = int(db.execute(count_stmt).scalar_one())
        rows = db.execute(
            stmt.order_by(ValidationRun.created_at.desc(), ValidationRun.id.desc())
            .offset(offset)
            .limit(limit)
        ).scalars().all()
        return list(rows), total

    @staticmethod
    def recent(db: Session, limit: int = 5) -> list[ValidationRun]:
        rows = db.execute(
            select(ValidationRun)
            .where(ValidationRun.status.in_(("succeeded", "failed")))
            .order_by(ValidationRun.created_at.desc())
            .limit(limit)
        ).scalars().all()
        return list(rows)

    @staticmethod
    def average_score(db: Session) -> float | None:
        value = db.execute(
            select(func.avg(ValidationRun.score)).where(ValidationRun.status == "succeeded")
        ).scalar_one_or_none()
        return float(value) if value is not None else None

    # ---------- 任务文档 ----------
    @staticmethod
    def add_documents(db: Session, documents: list[ValidationDocument]) -> None:
        if documents:
            db.add_all(documents)
            db.flush()

    @staticmethod
    def list_documents(db: Session, run_id: int) -> list[ValidationDocument]:
        return list(
            db.execute(
                select(ValidationDocument).where(ValidationDocument.run_id == run_id)
            ).scalars().all()
        )

    @staticmethod
    def list_documents_by_runs(db: Session, run_ids: list[int]) -> list[ValidationDocument]:
        if not run_ids:
            return []
        return list(
            db.execute(
                select(ValidationDocument).where(ValidationDocument.run_id.in_(run_ids))
            ).scalars().all()
        )

    # ---------- 发现 ----------
    @staticmethod
    def add_findings(db: Session, findings: list[Finding]) -> None:
        if findings:
            db.add_all(findings)
            db.flush()

    @staticmethod
    def list_findings(db: Session, run_id: int) -> list[Finding]:
        return list(
            db.execute(
                select(Finding)
                .where(Finding.run_id == run_id)
                .order_by(Finding.sort_order.asc(), Finding.id.asc())
            ).scalars().all()
        )

    @staticmethod
    def count_failed_by_severity(db: Session) -> dict[str, int]:
        """按严重程度统计全库未通过项，单条 GROUP BY 完成。"""
        rows = db.execute(
            select(Finding.severity, func.count(Finding.id))
            .where(Finding.passed.is_(False), Finding.source == SOURCE_RULE)
            .group_by(Finding.severity)
        ).all()
        return {str(severity): int(count) for severity, count in rows}

    @staticmethod
    def top_failed_rules(db: Session, limit: int = 5) -> list[tuple[str, str, int]]:
        """统计出现次数最多的未通过规则。"""
        rows = db.execute(
            select(Finding.rule_id, Finding.title, func.count(Finding.id).label("cnt"))
            .where(Finding.passed.is_(False), Finding.source == SOURCE_RULE)
            .group_by(Finding.rule_id, Finding.title)
            .order_by(func.count(Finding.id).desc())
            .limit(limit)
        ).all()
        return [(str(rule_id), str(title), int(count)) for rule_id, title, count in rows]

    @staticmethod
    def passed_count(db: Session) -> int:
        return int(
            db.execute(
                select(func.count(Finding.id)).where(Finding.status == STATUS_PASS)
            ).scalar_one()
        )
