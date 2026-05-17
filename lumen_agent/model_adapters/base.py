"""模型适配器抽象：统一内部消息格式 ↔ 模型格式。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any


class ModelAdapter(ABC):
    """模型适配器抽象基类。"""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None = None,
    ) -> str:
        """非流式对话。"""
        ...

    @abstractmethod
    def chat_stream(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None = None,
    ) -> AsyncIterator[tuple[str, str]]:
        """流式对话。"""
        ...
