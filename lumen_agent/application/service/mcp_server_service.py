"""MCP Server 管理服务：CRUD 编排、连接管理、测试等全部业务逻辑。"""

from __future__ import annotations

import logging
from typing import Any

from lumen_agent.api.schemas.mcp_dtos import (
    MCPServerCreate,
    MCPServerResponse,
    MCPServerTestResult,
    MCPServerUpdate,
)
from lumen_agent.infrastructure.data_base.sqlite_mcp import SqliteMCPServerRepository
from lumen_agent.model_adapters.client import MCPConnection, get_mcp_manager

logger = logging.getLogger(__name__)


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


async def list_mcp_servers(repo: SqliteMCPServerRepository) -> list[MCPServerResponse]:
    """列出所有已配置的 MCP Server。"""
    servers = await repo.list_all()
    return [_to_response(svr) for svr in servers]


async def create_mcp_server(
    repo: SqliteMCPServerRepository,
    body: MCPServerCreate,
) -> MCPServerResponse:
    """新增 MCP Server 配置，enabled 时自动连接。"""
    server = await repo.create(body.model_dump())
    logger.info("MCP Server 已创建：%s（%s）", server["name"], server["url"])

    if server["enabled"]:
        mgr = get_mcp_manager()
        ok = await mgr.connect_one(server["id"], server["url"], server.get("api_key") or None)
        logger.info("MCP Server %s 连接%s", server["name"], "成功" if ok else "失败")

    return _to_response(server)


async def get_mcp_server(
    repo: SqliteMCPServerRepository,
    server_id: str,
) -> MCPServerResponse | None:
    """查看单个 MCP Server 配置。未找到返回 None。"""
    server = await repo.get(server_id)
    return _to_response(server) if server else None


async def update_mcp_server(
    repo: SqliteMCPServerRepository,
    server_id: str,
    body: MCPServerUpdate,
) -> MCPServerResponse | None:
    """更新 MCP Server 配置，变更 URL/api_key/enabled 时自动重连。未找到返回 None。

    Raises:
        ValueError: 没有需要更新的字段。
    """
    update_data = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update_data:
        raise ValueError("没有需要更新的字段")

    server = await repo.update(server_id, update_data)
    if server is None:
        return None

    logger.info("MCP Server %s 配置已更新", server["name"])

    mgr = get_mcp_manager()
    if server["enabled"]:
        ok = await mgr.reconnect(server_id, server["url"], server.get("api_key") or None)
        logger.info("MCP Server %s 重连%s", server["name"], "成功" if ok else "失败")
    else:
        await mgr.disconnect(server_id)
        logger.info("MCP Server %s 已断开", server["name"])

    return _to_response(server)


async def delete_mcp_server(
    repo: SqliteMCPServerRepository,
    server_id: str,
) -> bool:
    """删除 MCP Server 配置，同时断开连接。未找到返回 False。"""
    mgr = get_mcp_manager()
    await mgr.disconnect(server_id)

    deleted = await repo.delete(server_id)
    if not deleted:
        return False

    logger.info("MCP Server %s 已删除", server_id)
    return True


async def test_mcp_server(
    repo: SqliteMCPServerRepository,
    server_id: str,
) -> MCPServerTestResult | None:
    """测试 MCP Server 连接是否正常（临时连接，不保持）。未找到返回 None。"""
    server = await repo.get(server_id)
    if server is None:
        return None

    conn = MCPConnection(server["url"], server.get("api_key") or None)
    try:
        await conn.connect()
        tools = await conn.list_tools()
        await conn.close()
        logger.info("MCP Server %s 测试通过，%d 个工具", server["name"], len(tools))
        return MCPServerTestResult(status="ok", tools_count=len(tools))
    except Exception as e:
        logger.warning("MCP Server %s 测试失败: %s", server["name"], e)
        return MCPServerTestResult(status="error", message=str(e))
