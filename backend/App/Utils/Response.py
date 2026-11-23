"""统一响应结构：{code, message, data}。"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "success"
    data: T | None = None


def success(data: Any = None, message: str = "success") -> dict[str, Any]:
    """成功响应。"""
    return {"code": 0, "message": message, "data": data}


def failure(code: int, message: str, data: Any = None) -> dict[str, Any]:
    """失败响应（由异常中间件调用）。"""
    return {"code": code, "message": message, "data": data}
