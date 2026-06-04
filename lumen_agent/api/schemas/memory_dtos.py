"""记忆文件 API DTO。"""

from __future__ import annotations

from pydantic import BaseModel


class MemoryFileItem(BaseModel):
    """单个记忆文件的元信息和内容。"""

    file_name: str
    """文件名，如 MEMORY.md、2026-05-26.md。"""

    content: str
    """文件的完整文本内容。"""

    type: str
    """文件类型：long_term（MEMORY.md）或 daily（每日记忆）。"""
