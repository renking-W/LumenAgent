"""MCP 工具索引调试 API DTO。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MCPToolSearchRequest(BaseModel):
    """POST /v1/mcp/tools/search 请求体。"""

    query: str = Field(..., min_length=1, description="检索 query")
    top_k: int | None = Field(default=None, ge=1, le=50)
    server_ids: list[str] | None = Field(default=None, description="限定 server id 列表")
    similarity_threshold: float | None = Field(default=None, ge=0.0, le=1.0)


class MCPToolSearchResponse(BaseModel):
    """向量检索结果：Chroma 命中后回表组装的 tool 详情。"""

    query: str
    top_k: int
    total_hits: int
    results: list[dict[str, Any]]


class MCPToolListItem(BaseModel):
    """已索引 tool 的摘要信息。"""

    tool_id: str
    server_id: str
    server_kind: str
    server_name: str
    tool_name: str
    description: str
    parameters: dict[str, Any]


class MCPToolDetail(MCPToolListItem):
    """单条 tool 完整记录（含 search_doc，供调试）。"""

    search_doc: str = ""
    schema_hash: str = ""
    created_at: str | None = None
    updated_at: str | None = None


class MCPToolSyncResponse(BaseModel):
    """sync 接口响应。"""

    tools_synced: int
    message: str = "ok"
