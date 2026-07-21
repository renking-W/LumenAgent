"""HTTP JSON：对话请求 / 响应体与会话 REST DTO。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class FileAttachment(BaseModel):
    """用户上传文件的结构化元数据。"""

    name: str = Field(min_length=1, max_length=255)
    path: str = Field(min_length=1)
    extension: str = ""
    size: int = Field(default=0, ge=0)
    content_type: str = "application/octet-stream"
    url: str = ""

class ChatRequest(BaseModel):
    """``POST /v1/chat`` / ``POST /v1/chat/stream``。"""

    message: str = ""
    session_id: str | None = Field(default=None, min_length=1)
    session_kind: int | None = None
    mode: Literal["simple", "agent"] = "agent"
    mcp_server_ids: list[str] = Field(
        default_factory=list,
        description="（可选）MCP Server ID；留空时后端自动加载全部已启用的 MCP",
    )
    self_system: str | None = Field(
        default=None,
        description="用户自定义系统提示语",
    )
    approval_mode: Literal["none", "all", "dangerous"] = "dangerous"
    image_urls: list[str] | None = Field(
        default=None,
        description="本轮附带的图片 URL 列表（来自 /v1/upload 返回的 url），仅 agent 模式下生效",
    )
    file_attachments: list[FileAttachment] = Field(
        default_factory=list,
        description="本轮上传文件的结构化元数据，供消息展示和 Agent 读取本地路径",
    )

    @model_validator(mode="after")
    def validate_message_content(self) -> "ChatRequest":
        """文字、图片和文件至少提供一种。"""
        if not self.message.strip() and not self.image_urls and not self.file_attachments:
            raise ValueError("message、image_urls 和 file_attachments 至少提供一个")
        return self


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
    kind: int = 0


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
    image_url: dict[str, str] | None = None
    path: str | None = None
    extension: str | None = None
    size: int | None = None
    content_type: str | None = None
    url: str | None = None


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
    kind: int = 0
