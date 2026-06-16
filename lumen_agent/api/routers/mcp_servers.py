"""MCP Server 配置管理 CRUD 路由：纯 HTTP 编排，全部业务逻辑委托给 mcp_server_service。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from lumen_agent.api.dependency import get_settings
from lumen_agent.api.schemas.mcp_dtos import (
    MCPServerCreate,
    MCPServerResponse,
    MCPServerTestResult,
    MCPServerUpdate,
)
from lumen_agent.application.service.mcp_server_service import (
    create_mcp_server as svc_create,
    delete_mcp_server as svc_delete,
    get_mcp_server as svc_get,
    list_mcp_servers as svc_list,
    test_mcp_server as svc_test,
    update_mcp_server as svc_update,
)
from lumen_agent.config import Settings, resolve_db_path
from lumen_agent.infrastructure.data_base.sqlite_mcp import SqliteMCPServerRepository

router = APIRouter(prefix="/v1/mcp/servers", tags=["mcp"])


def _get_repo(settings: Settings = Depends(get_settings)) -> SqliteMCPServerRepository:
    return SqliteMCPServerRepository(resolve_db_path(settings))


@router.get("", response_model=list[MCPServerResponse])
async def list_mcp_servers(
    repo: SqliteMCPServerRepository = Depends(_get_repo),
) -> list[MCPServerResponse]:
    return await svc_list(repo)


@router.post("", response_model=MCPServerResponse, status_code=status.HTTP_201_CREATED)
async def create_mcp_server(
    body: MCPServerCreate,
    repo: SqliteMCPServerRepository = Depends(_get_repo),
) -> MCPServerResponse:
    return await svc_create(repo, body)


@router.get("/{server_id}", response_model=MCPServerResponse)
async def get_mcp_server(
    server_id: str,
    repo: SqliteMCPServerRepository = Depends(_get_repo),
) -> MCPServerResponse:
    result = await svc_get(repo, server_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="MCP Server 不存在")
    return result


@router.put("/{server_id}", response_model=MCPServerResponse)
async def update_mcp_server(
    server_id: str,
    body: MCPServerUpdate,
    repo: SqliteMCPServerRepository = Depends(_get_repo),
) -> MCPServerResponse:
    try:
        result = await svc_update(repo, server_id, body)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="MCP Server 不存在")
    return result


@router.delete("/{server_id}")
async def delete_mcp_server(
    server_id: str,
    repo: SqliteMCPServerRepository = Depends(_get_repo),
) -> dict:
    deleted = await svc_delete(repo, server_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="MCP Server 不存在")
    return {"status": "deleted", "server_id": server_id}


@router.post("/{server_id}/test", response_model=MCPServerTestResult)
async def test_mcp_server(
    server_id: str,
    repo: SqliteMCPServerRepository = Depends(_get_repo),
) -> MCPServerTestResult:
    result = await svc_test(repo, server_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="MCP Server 不存在")
    return result
