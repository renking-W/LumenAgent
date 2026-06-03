"""统一接口：`Protocol` 描述 LLM 等依赖抽象（结构子类型，无框架依赖）。后续如果新增模型需要实现该接口"""

from collections.abc import AsyncIterator
from typing import Any, Protocol, TypedDict, runtime_checkable


class SessionRow(TypedDict):
    """会话元数据行（不含摘要状态）。"""

    id: str
    created_at: str
    updated_at: str
    title: str


class SessionFullRow(TypedDict):
    """完整会话行：含滑动窗口摘要状态 ``count`` / ``summary``。"""

    id: str
    created_at: str
    updated_at: str
    count: int
    summary: str
    title: str


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
    ) -> AsyncIterator[tuple[str, str]]:
        """流式对话：逐段 yield ``(kind, delta)``。

        ``kind`` 取值：``"content"``（正文）/ ``"reasoning_content"``（思维链）。
        """
        ...


@runtime_checkable
class ConversationRepositoryPort(Protocol):
    """会话与消息的持久化端口（实现可为 SQLite 等）。"""

    async def ensure_session(self, session_id: str) -> None:
        """若不存在则创建会话行（幂等）。"""
        ...

    async def list_messages(
        self,
        session_id: str,
        *,
        is_all: bool = True,
    ) -> list[dict[str, Any]]:
        """按时间顺序返回 ``role`` / ``content`` / ``created_at`` / ``updated_at`` 消息列表。

        参数:
            is_all: True(默认)=筛选仅有效消息; False=返回全部(含中断消息)。
        """
        ...

    async def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        status: int = 1,
    ) -> None:
        """在会话末尾追加一条消息并更新会话更新时间。

        status: 1=有效, 0=无效(中断).
        """
        ...

    async def list_sessions(self, *, limit: int = 50, offset: int = 0) -> list[SessionRow]:
        """分页列出会话元数据（通常按更新时间倒序）。"""
        ...

    async def get_session(self, session_id: str) -> SessionFullRow | None:
        """查询单个会话完整状态（含 ``count`` / ``summary``）。"""
        ...

    async def list_recent_messages(
        self,
        session_id: str,
        n_messages: int,
        *,
        is_all: bool = True,
    ) -> list[dict[str, Any]]:
        """按 ``seq`` 取最近 ``n_messages`` 条消息（返回时按时间正序），
        每条含 ``role`` / ``content`` / ``created_at`` / ``updated_at``。

        参数:
            is_all: True(默认)=筛选仅有效消息; False=返回全部(含中断消息)。
        """
        ...

    async def update_summary(
        self,
        session_id: str,
        *,
        new_summary: str,
        new_count: int,
    ) -> None:
        """单事务更新会话摘要与轮次计数。"""
        ...

    async def increment_round_counter(self, session_id: str) -> int:
        """轮次 +1（助手落库后调用），返回新的 ``count``。"""
        ...

    async def delete_session(self, session_id: str) -> bool:
        """删除会话及其全部消息。返回是否实际删除（不存在返回 False）。"""
        ...

    async def update_session_title(self, session_id: str, title: str) -> None:
        """更新会话标题。"""
        ...

    async def list_messages_before(
        self,
        session_id: str,
        limit: int,
        before_seq: int | None = None,
    ) -> list[dict[str, Any]]:
        """游标分页：取 ``seq < before_seq`` 的最新 ``limit`` 条消息。"""
        ...

@runtime_checkable
class KnowledgeRepositoryPort(Protocol):
    """知识库持久化端口（实现可为 SQLite 等）。"""

    async def ensure_knowledge(self, knowledge_id: str) -> None:
        """若不存在则创建知识行（幂等）。"""
        ...

    async def list_knowledges(self) -> list[dict[str, Any]]:
        """列出所有知识行。"""
        ...

    async def append_knowledge(self, knowledge_id: str, content: str) -> None:
        """在知识末尾追加一条内容并更新知识更新时间。"""