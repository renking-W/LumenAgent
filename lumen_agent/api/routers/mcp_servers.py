"""MCP Server 配置管理 CRUD 路由。"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status

from lumen_agent.api.dependency import get_settings
from lumen_agent.api.schemas.mcp_dtos import (
    MCPServerCreate,
    MCPServerResponse,
    MCPServerTestResult,
    MCPServerUpdate,
)
from lumen_agent.config import Settings, resolve_db_path
from lumen_agent.infrastructure.client.mcp_client import MCPConnection, get_mcp_manager
from lumen_agent.infrastructure.data_base.sqlite_mcp import SqliteMCPServerRepository

router = APIRouter(prefix="/v1/mcp/servers", tags=["mcp"])
_logger = logging.getLogger(__name__)


def _get_repo(settings: Settings = Depends(get_settings)) -> SqliteMCPServerRepository:
    """注入 MCP Server 配置仓储。"""
    return SqliteMCPServerRepository(resolve_db_path(settings))


@router.get("", response_model=list[MCPServerResponse])
async def list_mcp_servers(
    repo: SqliteMCPServerRepository = Depends(_get_repo),
) -> list[MCPServerResponse]:
    """列出所有已配置的 MCP Server。"""
    servers = await repo.list_all()
    # 附上连接状态
    mgr = get_mcp_manager()
    result: list[MCPServerResponse] = []
    for svr in servers:
        data = _to_response(svr)
        # 只在响应中附加连接状态，不做字段定义变更
        result.append(data)
    return result


@router.post("", response_model=MCPServerResponse, status_code=status.HTTP_201_CREATED)
async def create_mcp_server(
    body: MCPServerCreate,
    repo: SqliteMCPServerRepository = Depends(_get_repo),
) -> MCPServerResponse:
    """新增 MCP Server 配置，enabled 时自动连接。"""
    server = await repo.create(body.model_dump())
    _logger.info("MCP Server 已创建：%s（%s）", server["name"], server["url"])

    if server["enabled"]:
        mgr = get_mcp_manager()
        ok = await mgr.connect_one(server["id"], server["url"], server.get("api_key") or None)
        _logger.info("MCP Server %s 连接%s", server["name"], "成功" if ok else "失败")

    return _to_response(server)


@router.get("/{server_id}", response_model=MCPServerResponse)
async def get_mcp_server(
    server_id: str,
    repo: SqliteMCPServerRepository = Depends(_get_repo),
) -> MCPServerResponse:
    """查看单个 MCP Server 配置。"""
    server = await repo.get(server_id)
    if server is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="MCP Server 不存在")
    return _to_response(server)


@router.put("/{server_id}", response_model=MCPServerResponse)
async def update_mcp_server(
    server_id: str,
    body: MCPServerUpdate,
    repo: SqliteMCPServerRepository = Depends(_get_repo),
) -> MCPServerResponse:
    """更新 MCP Server 配置，变更 URL/api_key/enabled 时自动重连。"""
    update_data = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="没有需要更新的字段")

    server = await repo.update(server_id, update_data)
    if server is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="MCP Server 不存在")

    _logger.info("MCP Server %s 配置已更新", server["name"])

    # 根据 enabled 状态决定连接或断开
    mgr = get_mcp_manager()
    if server["enabled"]:
        ok = await mgr.reconnect(server_id, server["url"], server.get("api_key") or None)
        _logger.info("MCP Server %s 重连%s", server["name"], "成功" if ok else "失败")
    else:
        await mgr.disconnect(server_id)
        _logger.info("MCP Server %s 已断开", server["name"])

    return _to_response(server)


@router.delete("/{server_id}")
async def delete_mcp_server(
    server_id: str,
    repo: SqliteMCPServerRepository = Depends(_get_repo),
) -> dict:
    """删除 MCP Server 配置，同时断开连接。"""
    mgr = get_mcp_manager()
    await mgr.disconnect(server_id)

    deleted = await repo.delete(server_id)
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="MCP Server 不存在")

    _logger.info("MCP Server %s 已删除", server_id)
    return {"status": "deleted", "server_id": server_id}


@router.post("/{server_id}/test", response_model=MCPServerTestResult)
async def test_mcp_server(
    server_id: str,
    repo: SqliteMCPServerRepository = Depends(_get_repo),
) -> MCPServerTestResult:
    """测试 MCP Server 连接是否正常（临时连接，不保持）。"""
    server = await repo.get(server_id)
    if server is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="MCP Server 不存在")

    conn = MCPConnection(server["url"], server.get("api_key") or None)
    try:
        await conn.connect()
        tools = await conn.list_tools()
        await conn.close()
        _logger.info("MCP Server %s 测试通过，%d 个工具", server["name"], len(tools))
        return MCPServerTestResult(status="ok", tools_count=len(tools))
    except Exception as e:
        _logger.warning("MCP Server %s 测试失败: %s", server["name"], e)
        return MCPServerTestResult(status="error", message=str(e))


def _to_response(server: dict) -> MCPServerResponse:
    """将仓储层 dict 转为 DTO。"""
    return MCPServerResponse(
        id=server["id"],
        name=server["name"],
        url=server["url"],
        api_key=server.get("api_key") or None,
        enabled=bool(server["enabled"]),
        created_at=server["created_at"],
        updated_at=server["updated_at"],
    )
