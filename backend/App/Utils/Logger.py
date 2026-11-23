"""统一日志配置。

要求（见 AGENTS.md 第 8 章）：
- 统一使用 logging，禁止 print；
- 同时输出控制台与按日期轮转的文件；
- 日志中不得出现密码、令牌、密钥等敏感信息。
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | rid=%(request_id)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_CONFIGURED = False


class _RequestIdFilter(logging.Filter):
    """把当前请求 id 注入日志记录，便于按请求串联排查。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configure_logging(log_dir: Path, level: str) -> None:
    """初始化根日志器，重复调用不会重复挂载 handler。"""
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
    id_filter = _RequestIdFilter()

    console_handler = logging.StreamHandler(stream=sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(id_filter)

    file_handler = TimedRotatingFileHandler(
        filename=str(log_dir / "App.log"),
        when="midnight",
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(id_filter)

    error_handler = TimedRotatingFileHandler(
        filename=str(log_dir / "Error.log"),
        when="midnight",
        backupCount=30,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    error_handler.addFilter(id_filter)

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level, logging.INFO))
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(error_handler)

    # 降低第三方库噪音
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """获取命名日志器。"""
    return logging.getLogger(name)
