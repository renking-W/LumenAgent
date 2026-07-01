"""stdio MCP Server 管理相关的请求/响应 DTO。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class MCPStdioServerCreate(BaseModel):
    """创建 stdio MCP Server 配置。"""

    name: str = Field(..., min_length=1, max_length=100, description="显示名称")
    command: str = Field(..., description="启动命令，如 npx / python / node")
    args: list[str] = Field(default=[], description="命令行参数列表")
    env: dict[str, str] = Field(default={}, description="额外环境变量")
    cwd: str | None = Field(default=None, description="工作目录（空则继承进程目录）")
    enabled: bool = Field(default=True, description="是否启用")


class MCPStdioServerUpdate(BaseModel):
    """更新 stdio MCP Server 配置（全部可选）。"""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    cwd: str | None = None
    enabled: bool | None = None


class MCPStdioServerResponse(BaseModel):
    """stdio MCP Server 配置响应。"""

    id: str
    name: str
    command: str
    args: list[str]
    env: dict[str, str]
    cwd: str
    enabled: bool
    created_at: str
    updated_at: str
