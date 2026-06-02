"""模型适配器抽象：统一内部消息格式 ↔ 模型格式。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable, Awaitable
from typing import Any

from lumen_agent.infrastructure.http_pool import StreamHandle

# 连接建立后的回调类型（适配层透传至 HTTP 客户端）
StreamHandleCallback = Callable[[StreamHandle], Awaitable[None]]


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
        tools: list[dict] | None = None,
        temperature: float | None = None,
        on_connect: StreamHandleCallback | None = None,
    ) -> AsyncIterator[tuple[str, str | dict]]:
        """流式对话。

        yield (kind, data):
          ("content", str)              – 文本增量
          ("reasoning_content", str)    – 思维链增量
          ("tool_use", dict)            – 工具调用块（仅当 tools 不为 None 且模型发起调用时）

        tools 为 None 时行为与旧版完全一致（不向模型传工具定义）。

        参数:
            on_connect: 连接建立后的回调，接收 ``StreamHandle`` 供注册到中断注册表。
        """
        ...
