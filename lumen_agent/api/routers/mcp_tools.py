"""MCP 工具索引调试与同步路由：纯 HTTP 编排，业务逻辑委托给 query/sync service。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from lumen_agent.api.dependency import get_settings
from lumen_agent.api.schemas.mcp_tool_dtos import (
    MCPToolDetail,
    MCPToolListItem,
    MCPToolSearchRequest,
    MCPToolSearchResponse,
    MCPToolSyncResponse,
)
from lumen_agent.application.service.mcp.mcp_tool_query_service import McpToolQueryService
from lumen_agent.application.service.mcp.mcp_tool_sync_service import McpToolSyncService
from lumen_agent.config import Settings

router = APIRouter(prefix="/v1/mcp/tools", tags=["mcp-tools"])


def _query_service(settings: Settings = Depends(get_settings)) -> McpToolQueryService:
    return McpToolQueryService(settings)


def _sync_service(settings: Settings = Depends(get_settings)) -> McpToolSyncService:
    return McpToolSyncService(settings)


@router.post("/search", response_model=MCPToolSearchResponse)
async def search_mcp_tools(
    body: MCPToolSearchRequest,
    service: McpToolQueryService = Depends(_query_service),
) -> MCPToolSearchResponse:
    """向量检索调试：与 Agent 的 mcp_search 共用同一套 query 逻辑。"""
    payload = await service.search_tools(
        body.query,
        top_k=body.top_k,
        server_ids=body.server_ids,
        similarity_threshold=body.similarity_threshold,
    )
    return MCPToolSearchResponse(**payload)


@router.get("", response_model=list[MCPToolListItem])
async def list_mcp_tools(
    server_id: str | None = Query(default=None),
    server_kind: str | None = Query(default=None, pattern="^(http|stdio)$"),
    server_ids: list[str] | None = Query(default=None),
    service: McpToolQueryService = Depends(_query_service),
) -> list[MCPToolListItem]:
    """列出已索引 tool，可按 server 过滤。"""
    rows = await service.list_tools(
        server_kind=server_kind,
        server_id=server_id,
        server_ids=server_ids,
    )
    return [MCPToolListItem(**row) for row in rows]


@router.get("/{tool_id}", response_model=MCPToolDetail)
async def get_mcp_tool(
    tool_id: str,
    service: McpToolQueryService = Depends(_query_service),
) -> MCPToolDetail:
    """查看单条 tool 的 DB 记录（含 search_doc、input_schema）。"""
    row = await service.get_tool(tool_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="tool not found")
    return MCPToolDetail(**row)


@router.post("/sync-all", response_model=MCPToolSyncResponse)
async def sync_all_mcp_tools(
    service: McpToolSyncService = Depends(_sync_service),
) -> MCPToolSyncResponse:
    """对所有 enabled 且已连接的 MCP Server 全量重建工具索引。"""
    count = await service.sync_all_enabled()
    return MCPToolSyncResponse(tools_synced=count)


@router.post("/servers/{server_kind}/{server_id}/sync-tools", response_model=MCPToolSyncResponse)
async def sync_server_mcp_tools(
    server_kind: str,
    server_id: str,
    service: McpToolSyncService = Depends(_sync_service),
) -> MCPToolSyncResponse:
    """手动触发单个 server 的工具索引重建（server_kind: http | stdio）。"""
    if server_kind not in ("http", "stdio"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="server_kind must be http or stdio")
    try:
        count = await service.sync_server(server_kind, server_id)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    return MCPToolSyncResponse(tools_synced=count)
