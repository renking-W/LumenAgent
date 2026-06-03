"""HTTP JSON：对话请求 / 响应体与会话 REST DTO。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """``POST /v1/chat`` / ``POST /v1/chat/stream``。

    ``session_id`` 可选，缺省由服务端生成。
    ``mode`` 控制处理路径：
      - ``"simple"``（默认）：单轮流式对话，无工具调用
      - ``"agent"``：多轮 Agent 工具循环
    """

    message: str = Field(..., min_length=1)
    session_id: str | None = Field(default=None, min_length=1)
    mode: Literal["simple", "agent"] = "simple"


class ChatResponse(BaseModel):
    """整段对话响应，回传 ``session_id`` 便于客户端续接。"""

    content: list[ContentBlock]
    session_id: str


class SessionSummary(BaseModel):
    """会话列表项（基础元数据）。"""

    id: str
    created_at: str
    updated_at: str
    title: str = ""


class ContentBlock(BaseModel):
    """统一内容块。"""

    type: str
    text: str | None = None
    thinking: str | None = None
    id: str | None = None
    name: str | None = None
    input: dict[str, Any] | None = None
    tool_use_id: str | None = None
    content: str | None = None
    is_error: bool | None = None


class StoredMessage(BaseModel):
    """单条历史消息（含 seq 游标、时间戳和状态）。"""

    seq: int
    role: str
    content: list[ContentBlock]
    created_at: str
    updated_at: str
    status: int


class InterruptRequest(BaseModel):
    """``POST /v1/chat/stream/interrupt`` 请求体。"""

    session_id: str


class AppendMessageRequest(BaseModel):
    """``POST /v1/sessions/{session_id}/messages`` 请求体。"""

    role: str
    content: str | list[dict[str, Any]]
    status: int = 1


class UpdateTitleRequest(BaseModel):
    """``PUT /v1/sessions/{session_id}/title`` 请求体。"""

    title: str = Field(..., min_length=1, max_length=100)


class SessionSummaryDetail(BaseModel):
    """会话摘要明细：当前已压缩摘要 + 未摘要轮次计数。"""

    session_id: str
    summary: str
    count: int
    title: str = ""
