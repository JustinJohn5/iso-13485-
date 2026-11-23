"""用户数据访问。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from App.Models.User import User


class UserDao:
    """用户表读写。"""

    @staticmethod
    def get_by_email(db: Session, email: str) -> User | None:
        return db.execute(select(User).where(User.email == email.lower())).scalar_one_or_none()

    @staticmethod
    def get_by_id(db: Session, user_id: int) -> User | None:
        return db.get(User, user_id)

    @staticmethod
    def create(
        db: Session,
        *,
        email: str,
        display_name: str,
        password_hash: str,
        role: str,
    ) -> User:
        user = User(
            email=email.lower(),
            display_name=display_name or email,
            password_hash=password_hash,
            role=role,
        )
        db.add(user)
        db.flush()
        return user

    @staticmethod
    def update_password(db: Session, user: User, password_hash: str) -> None:
        user.password_hash = password_hash
        user.token_version = (user.token_version or 1) + 1
        user.updated_at = datetime.now()

    @staticmethod
    def bump_token_version(db: Session, user: User) -> None:
        user.token_version = (user.token_version or 1) + 1

    @staticmethod
    def count(db: Session) -> int:
        return int(db.execute(select(func.count(User.id))).scalar_one())

    @staticmethod
    def list_all(db: Session) -> list[User]:
        return list(db.execute(select(User).order_by(User.id.asc())).scalars().all())
