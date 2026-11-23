"""上传文件模型。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from App.Db.Base import Base
from App.Utils.TimeUtils import now

TEXT_STATUS_OK = "ok"
TEXT_STATUS_INSUFFICIENT = "insufficient"
TEXT_STATUS_FAILED = "failed"


class UploadedFile(Base):
    """上传的质量体系文档及其抽取出的纯文本。"""

    __tablename__ = "uploaded_files"
    __table_args__ = {"comment": "上传文档"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    file_uid: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, comment="对外文件标识")
    original_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="原始文件名")
    stored_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="落盘随机文件名")
    extension: Mapped[str] = mapped_column(String(16), nullable=False, comment="小写扩展名")
    document_type: Mapped[str] = mapped_column(String(48), nullable=False, comment="质量体系文档类型")
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False, comment="规范 MIME")
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="文件字节数")
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="内容摘要")
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="页数/工作表数")
    char_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="抽取字符数")
    text_status: Mapped[str] = mapped_column(String(24), nullable=False, default=TEXT_STATUS_OK, comment="文本抽取状态")
    extracted_text: Mapped[str] = mapped_column(
        Text().with_variant(LONGTEXT, "mysql"), nullable=False, default="", comment="抽取的纯文本"
    )
    uploaded_by: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True, comment="上传人用户 id")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now, index=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<UploadedFile id={self.id} name={self.original_name}>"
