"""按用户隔离的文件分组与既有上传文件引用。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from App.Db.Base import Base
from App.Utils.TimeUtils import now


class FileGroup(Base):
    __tablename__ = 'file_groups'
    __table_args__ = (
        UniqueConstraint('owner_id', 'name_identity', name='uq_file_groups_owner_name'),
        Index('ix_file_groups_owner_created', 'owner_id', 'created_at'),
        {'comment': '个人文件分组'},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    group_uid: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    name_identity: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now)


class FileGroupMember(Base):
    __tablename__ = 'file_group_members'
    __table_args__ = (Index('ix_file_group_members_file', 'file_id'), {'comment': '个人分组的文件引用'})

    group_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('file_groups.id', ondelete='CASCADE'), primary_key=True)
    file_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('uploaded_files.id', ondelete='CASCADE'), primary_key=True)
