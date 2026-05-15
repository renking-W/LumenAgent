"""统一接口：`Protocol` 描述 LLM 等依赖抽象（结构子类型，无框架依赖）。后续如果新增模型需要实现该接口"""

from collections.abc import AsyncIterator
from typing import Any, Protocol, TypedDict, runtime_checkable


class SessionRow(TypedDict):
    id: str
    created_at: str
    updated_at: str


@runtime_checkable
class LLMClientPort(Protocol):
    """OpenAI Chat Completions 风格的 messages；`chat` 整段回复，`chat_stream` 流式回复。"""

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None = None,
    ) -> str:
        """非流式对话：一次返回完整助手文本。"""
        ...

    def chat_stream(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        """流式对话：逐段 yield 助手文本增量。"""
        ...


@runtime_checkable
class ConversationRepositoryPort(Protocol):
    """会话与消息的持久化端口（实现可为 SQLite 等）。"""

    async def ensure_session(self, session_id: str) -> None:
        """若不存在则创建会话行（幂等）。"""
        ...

    async def list_messages(self, session_id: str) -> list[dict[str, Any]]:
        """按时间顺序返回 ``role`` / ``content`` 消息列表。"""
        ...

    async def append_message(self, session_id: str, role: str, content: str) -> None:
        """在会话末尾追加一条消息并更新会话更新时间。"""
        ...

    async def list_sessions(self, *, limit: int = 50, offset: int = 0) -> list[SessionRow]:
        """分页列出会话元数据（通常按更新时间倒序）。"""
        ...
