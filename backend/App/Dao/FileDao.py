"""上传文件数据访问。"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from App.Models.UploadedFile import UploadedFile


class FileDao:
    """上传文档表读写。"""

    @staticmethod
    def create(db: Session, file: UploadedFile) -> UploadedFile:
        db.add(file)
        db.flush()
        return file

    @staticmethod
    def get_by_uid(db: Session, file_uid: str) -> UploadedFile | None:
        return db.execute(
            select(UploadedFile).where(UploadedFile.file_uid == file_uid)
        ).scalar_one_or_none()

    @staticmethod
    def get_by_uids(db: Session, file_uids: list[str]) -> list[UploadedFile]:
        """批量获取多个文档，避免校验流程逐份往返数据库。"""
        if not file_uids:
            return []
        rows = db.execute(
            select(UploadedFile).where(UploadedFile.file_uid.in_(file_uids))
        ).scalars().all()
        return list(rows)

    @staticmethod
    def get_by_ids(db: Session, file_ids: list[int]) -> list[UploadedFile]:
        """一次批量查询多个文档，避免循环内单条查询。"""
        if not file_ids:
            return []
        rows = db.execute(
            select(UploadedFile).where(UploadedFile.id.in_(file_ids))
        ).scalars().all()
        return list(rows)

    @staticmethod
    def list_paged(
        db: Session, *, offset: int, limit: int, keyword: str = ""
    ) -> tuple[list[UploadedFile], int]:
        stmt = select(UploadedFile)
        count_stmt = select(func.count(UploadedFile.id))
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(UploadedFile.original_name.like(like))
            count_stmt = count_stmt.where(UploadedFile.original_name.like(like))
        total = int(db.execute(count_stmt).scalar_one())
        rows = db.execute(
            stmt.order_by(UploadedFile.created_at.desc(), UploadedFile.id.desc())
            .offset(offset)
            .limit(limit)
        ).scalars().all()
        return list(rows), total

    @staticmethod
    def delete(db: Session, file: UploadedFile) -> None:
        db.delete(file)
        db.flush()

    @staticmethod
    def count(db: Session) -> int:
        return int(db.execute(select(func.count(UploadedFile.id))).scalar_one())
