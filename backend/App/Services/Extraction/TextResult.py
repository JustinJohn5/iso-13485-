"""文本抽取结果与公共常量。"""

from __future__ import annotations

from dataclasses import dataclass, field

# 低于该字符数时认为文本不足（扫描件、空文件、图片型 PDF）
MIN_TEXT_CHARS = 60

STATUS_OK = "ok"
STATUS_INSUFFICIENT = "insufficient"


@dataclass
class TextResult:
    """抽取结果。"""

    text: str
    page_count: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def char_count(self) -> int:
        return len(self.text.strip())

    @property
    def status(self) -> str:
        return STATUS_OK if self.char_count >= MIN_TEXT_CHARS else STATUS_INSUFFICIENT

    def preview(self, limit: int = 800) -> str:
        """截取正文预览，供前端确认文件内容。"""
        return self.text.strip()[:limit]
