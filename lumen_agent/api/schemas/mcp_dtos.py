"""MCP Server 管理相关的请求/响应 DTO。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class MCPServerCreate(BaseModel):
    """创建 MCP Server 配置。

    请求中的 description 为可选 user_hint；响应 MCPServerResponse.description
    为 AI 根据 tools 生成的最终说明。
    """

    name: str = Field(..., min_length=1, max_length=100, description="显示名称")
    url: str = Field(..., description="MCP Server SSE 端点 URL")
    api_key: str | None = Field(default=None, description="MCP Server 鉴权密钥")
    description: str | None = Field(
        default=None,
        description="可选参考说明，保存后由 AI 根据工具列表自动生成最终描述（≤400字）",
    )
    enabled: bool = Field(default=True, description="是否启用")


class MCPServerUpdate(BaseModel):
    """更新 MCP Server 配置（全部可选，只更新提供的字段）。"""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    url: str | None = None
    api_key: str | None = None
    description: str | None = Field(
        default=None,
        description="可选参考说明，保存后由 AI 根据工具列表自动生成最终描述（≤400字）",
    )
    enabled: bool | None = None


class MCPServerResponse(BaseModel):
    """MCP Server 配置响应。"""

    id: str
    name: str
    url: str
    api_key: str | None
    transport: str = ""
    description: str = ""
    enabled: bool
    created_at: str
    updated_at: str


class MCPServerTestResult(BaseModel):
    """MCP Server 连接测试结果。"""

    status: str  # "ok" | "error"
    message: str | None = None
    tools_count: int | None = None
    tools_synced: int | None = Field(default=None, description="测试成功后同步写入索引的 tool 数量")
