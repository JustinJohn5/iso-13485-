"""分页参数解析：全项目统一 page / page_size 约定。"""

from __future__ import annotations

from dataclasses import dataclass

MAX_PAGE_SIZE = 100


@dataclass(frozen=True)
class PageParams:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def parse_page(page: int | None, page_size: int | None) -> PageParams:
    """约束分页范围，非法值回落到默认值而不是报错。"""
    safe_page = page if isinstance(page, int) and page >= 1 else 1
    safe_size = page_size if isinstance(page_size, int) and page_size >= 1 else 10
    return PageParams(page=safe_page, page_size=min(safe_size, MAX_PAGE_SIZE))


def page_payload(items: list, total: int, params: PageParams) -> dict:
    """组装分页响应体。"""
    return {
        "items": items,
        "total": total,
        "page": params.page,
        "page_size": params.page_size,
        "total_pages": (total + params.page_size - 1) // params.page_size if total else 0,
    }
