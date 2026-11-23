"""时间工具：统一使用带时区的本地时间（Asia/Shanghai），入库为 naive datetime。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

LOCAL_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")


def now() -> datetime:
    """当前本地时间（去掉时区信息，与 MySQL DATETIME 对齐）。"""
    return datetime.now(tz=LOCAL_TZ).replace(tzinfo=None, microsecond=0)


def now_with_tz() -> datetime:
    """当前带时区时间，用于 JWT 与对外展示。"""
    return datetime.now(tz=LOCAL_TZ)


def to_iso(value: datetime | None) -> str | None:
    """转换为 ISO8601 字符串（本地时区）。"""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=LOCAL_TZ)
    return value.isoformat(timespec="seconds")


def parse_date(text: str) -> datetime | None:
    """解析常见的文档日期写法，失败返回 None。"""
    cleaned = text.strip().replace("年", "-").replace("月", "-").replace("日", "")
    cleaned = cleaned.replace("/", "-").replace(".", "-").strip()
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y%m%d"):
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return None
