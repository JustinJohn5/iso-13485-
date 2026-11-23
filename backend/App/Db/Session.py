"""数据库连接：MySQL 8.4 + SQLAlchemy 2.0 连接池。"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from App.Config.Settings import get_settings
from App.Utils.Logger import get_logger

logger = get_logger(__name__)

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """惰性创建全局引擎（连接串只来自环境变量）。"""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_recycle=3600,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            future=True,
        )
        logger.info("数据库引擎已创建：%s", _mask_dsn(settings.database_url))
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """惰性创建会话工厂。"""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(), autoflush=False, expire_on_commit=False, future=True
        )
    return _session_factory


@contextmanager
def session_scope() -> Iterator[Session]:
    """事务上下文：正常提交，异常回滚。"""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    """FastAPI 依赖：请求级会话。"""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def check_database() -> bool:
    """健康检查：验证数据库连通性。"""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001 - 健康检查不抛出
        logger.error("数据库连通性检查失败：%s", exc)
        return False


def _mask_dsn(dsn: str) -> str:
    """日志中隐藏数据库密码。"""
    if "://" not in dsn:
        return "***"
    scheme, rest = dsn.split("://", 1)
    if "@" not in rest:
        return f"{scheme}://***"
    credentials, host_part = rest.split("@", 1)
    user = credentials.split(":", 1)[0]
    return f"{scheme}://{user}:***@{host_part.split('?', 1)[0]}"
