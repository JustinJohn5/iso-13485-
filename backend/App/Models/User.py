"""用户模型。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from App.Db.Base import Base
from App.Utils.TimeUtils import now

ROLE_ADMIN = "admin"
ROLE_AUDITOR = "auditor"
ROLE_VIEWER = "viewer"
VALID_ROLES = (ROLE_ADMIN, ROLE_AUDITOR, ROLE_VIEWER)


class User(Base):
    """系统用户：管理员 / 审核员 / 只读用户。"""

    __tablename__ = "users"
    __table_args__ = {"comment": "系统用户"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(190), unique=True, nullable=False, comment="登录邮箱")
    display_name: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="显示名称")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, comment="bcrypt 密码哈希")
    role: Mapped[str] = mapped_column(String(16), nullable=False, default=ROLE_VIEWER, comment="角色")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否启用")
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="令牌版本号")
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="连续登录失败次数")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="锁定截止时间")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="最近登录时间")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=now, onupdate=now)

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"<User id={self.id} email={self.email} role={self.role}>"
