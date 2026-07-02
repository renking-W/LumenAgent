"""stdio MCP Server 配置管理 CRUD 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from lumen_agent.api.dependency import get_settings
from lumen_agent.api.schemas.mcp_dtos import MCPServerTestResult
from lumen_agent.api.schemas.mcp_stdio_dtos import (
    MCPStdioServerCreate,
    MCPStdioServerResponse,
    MCPStdioServerUpdate,
)
from lumen_agent.application.service.mcp_stdio_server_service import (
    create_stdio_server as svc_create,
    delete_stdio_server as svc_delete,
    get_stdio_server as svc_get,
    list_stdio_servers as svc_list,
    test_stdio_server as svc_test,
    update_stdio_server as svc_update,
)
from lumen_agent.config import Settings, resolve_db_path
from lumen_agent.infrastructure.data_base.sqlite_mcp_stdio import (
    SqliteMCPStdioServerRepository,
)

router = APIRouter(prefix="/v1/mcp/stdio-servers", tags=["mcp-stdio"])


def _get_repo(
    settings: Settings = Depends(get_settings),
) -> SqliteMCPStdioServerRepository:
    return SqliteMCPStdioServerRepository(resolve_db_path(settings))


@router.get("", response_model=list[MCPStdioServerResponse])
async def list_stdio_servers(
    repo: SqliteMCPStdioServerRepository = Depends(_get_repo),
) -> list[MCPStdioServerResponse]:
    return await svc_list(repo)


@router.post("", response_model=MCPStdioServerResponse, status_code=status.HTTP_201_CREATED)
async def create_stdio_server(
    body: MCPStdioServerCreate,
    repo: SqliteMCPStdioServerRepository = Depends(_get_repo),
) -> MCPStdioServerResponse:
    try:
        return await svc_create(repo, body)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{server_id}", response_model=MCPStdioServerResponse)
async def get_stdio_server(
    server_id: str,
    repo: SqliteMCPStdioServerRepository = Depends(_get_repo),
) -> MCPStdioServerResponse:
    result = await svc_get(repo, server_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="stdio MCP Server 不存在")
    return result


@router.put("/{server_id}", response_model=MCPStdioServerResponse)
async def update_stdio_server(
    server_id: str,
    body: MCPStdioServerUpdate,
    repo: SqliteMCPStdioServerRepository = Depends(_get_repo),
) -> MCPStdioServerResponse:
    try:
        result = await svc_update(repo, server_id, body)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="stdio MCP Server 不存在")
    return result


@router.delete("/{server_id}")
async def delete_stdio_server(
    server_id: str,
    repo: SqliteMCPStdioServerRepository = Depends(_get_repo),
) -> dict:
    deleted = await svc_delete(repo, server_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="stdio MCP Server 不存在")
    return {"status": "deleted", "server_id": server_id}


@router.post("/{server_id}/test", response_model=MCPServerTestResult)
async def test_stdio_server(
    server_id: str,
    repo: SqliteMCPStdioServerRepository = Depends(_get_repo),
) -> MCPServerTestResult:
    result = await svc_test(repo, server_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="stdio MCP Server 不存在")
    return result
