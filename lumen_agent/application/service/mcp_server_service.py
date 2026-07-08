"""MCP Server 管理服务：CRUD 编排、连接管理、测试等全部业务逻辑。

工具索引：创建/启用/更新 description/测试成功后调用 McpToolSyncService；
禁用时清理 Chroma + SQLite 中的 tool 记录。
"""

from __future__ import annotations

import logging
from typing import Any

from lumen_agent.api.schemas.mcp_dtos import (
    MCPServerCreate,
    MCPServerResponse,
    MCPServerTestResult,
    MCPServerUpdate,
)
from lumen_agent.application.service.mcp_lookup import (
    assert_name_available,
    assert_name_available_exclude,
)
from lumen_agent.application.service.mcp_tool_sync_service import McpToolSyncService
from lumen_agent.config import Settings, get_settings, resolve_db_path
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
        transport=server.get("transport") or "",
        description=server.get("description") or "",
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
    settings: Settings | None = None,
) -> MCPServerResponse:
    """新增 MCP Server 配置。

    若 enabled=True，先用临时连接验证可达性（探测 transport）；
    连接失败直接抛 ValueError，**不写入 DB**。
    验证通过后写 DB，再以已知 transport 直接注册到 manager（无需二次探测）。
    """
    if settings is None:
        settings = get_settings()
    await assert_name_available(resolve_db_path(settings), body.name)

    resolved_transport = ""

    if body.enabled:
        probe = MCPConnection(body.url, body.api_key or None, "")
        try:
            await probe.connect()
            resolved_transport = probe.resolved_transport
            await probe.close()
            logger.info(
                "MCP Server %s 预连接成功，transport=%s", body.name, resolved_transport
            )
        except Exception as e:
            logger.warning("MCP Server %s 连接验证失败: %s", body.url, e)
            raise ValueError(f"无法连接到 MCP Server：{e}") from e

    data = body.model_dump()
    data["transport"] = resolved_transport
    server = await repo.create(data)
    logger.info("MCP Server 已创建：%s（%s）", server["name"], server["url"])

    if server["enabled"]:
        mgr = get_mcp_manager()
        ok, _ = await mgr.connect_one(
            server["id"],
            server["url"],
            server.get("api_key") or None,
            resolved_transport,
        )
        if not ok:
            logger.warning("MCP Server %s 注册到 manager 失败（已保存配置）", server["name"])
        else:
            # 连接成功后同步 list_tools → SQLite + Chroma 索引
            try:
                synced = await McpToolSyncService(settings).sync_server("http", server["id"])
                logger.info("MCP Server %s 工具索引已同步：%s 个", server["name"], synced)
            except Exception:
                logger.exception("MCP Server %s 工具索引同步失败", server["name"])

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
    settings: Settings | None = None,
) -> MCPServerResponse | None:
    """更新 MCP Server 配置，变更 URL/api_key/enabled 时自动重连。

    - 若变更了 url 或 api_key，清空 transport 让下次连接重新探测。
    - 未找到返回 None。

    Raises:
        ValueError: 没有需要更新的字段。
    """
    if settings is None:
        settings = get_settings()
    update_data = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update_data:
        raise ValueError("没有需要更新的字段")
    if "name" in update_data:
        await assert_name_available_exclude(
            resolve_db_path(settings), update_data["name"], server_id
        )

    # url 或 api_key 变更则清空 transport，触发重新探测
    if "url" in update_data or "api_key" in update_data:
        update_data["transport"] = ""

    server = await repo.update(server_id, update_data)
    if server is None:
        return None

    logger.info("MCP Server %s 配置已更新", server["name"])

    mgr = get_mcp_manager()
    if server["enabled"]:
        ok, resolved = await mgr.reconnect(
            server_id,
            server["url"],
            server.get("api_key") or None,
            server.get("transport") or "",
        )
        logger.info(
            "MCP Server %s 重连%s transport=%s",
            server["name"],
            "成功" if ok else "失败",
            resolved,
        )
        if ok and resolved and resolved != server.get("transport", ""):
            await repo.update_transport(server_id, resolved)
            server["transport"] = resolved
    else:
        await mgr.disconnect(server_id)
        logger.info("MCP Server %s 已断开", server["name"])
        # 禁用时清理该 server 下全部 tool 索引
        try:
            await McpToolSyncService(settings).clear_server("http", server_id)
        except Exception:
            logger.exception("MCP Server %s 工具索引清理失败", server_id)

    # 启用或仅更新 description 时重新同步（description 写入 search_doc）
    if server["enabled"] or "description" in update_data:
        try:
            synced = await McpToolSyncService(settings).sync_server("http", server_id)
            logger.info("MCP Server %s 工具索引已同步：%s 个", server["name"], synced)
        except Exception:
            logger.exception("MCP Server %s 工具索引同步失败", server["name"])

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

    try:
        # 删除配置时一并清理 tool 索引
        await McpToolSyncService().clear_server("http", server_id)
    except Exception:
        logger.exception("MCP Server %s 工具索引清理失败", server_id)

    logger.info("MCP Server %s 已删除", server_id)
    return True


async def test_mcp_server(
    repo: SqliteMCPServerRepository,
    server_id: str,
) -> MCPServerTestResult | None:
    """测试 MCP Server 连接（临时连接，使用 DB 中已有 transport 加速）。未找到返回 None。"""
    server = await repo.get(server_id)
    if server is None:
        return None

    conn = MCPConnection(
        server["url"],
        server.get("api_key") or None,
        server.get("transport") or "",
    )
    try:
        await conn.connect()
        tools = await conn.list_tools()
        await conn.close()
        tools_synced = 0
        try:
            # 测试连接已 list_tools，直接传入避免重复请求
            tools_synced = await McpToolSyncService().sync_server(
                "http", server_id, tool_defs=tools
            )
        except Exception:
            logger.exception("MCP Server %s 测试后工具索引同步失败", server["name"])
        logger.info("MCP Server %s 测试通过，%d 个工具", server["name"], len(tools))
        return MCPServerTestResult(
            status="ok",
            tools_count=len(tools),
            tools_synced=tools_synced,
        )
    except Exception as e:
        logger.warning("MCP Server %s 测试失败: %s", server["name"], e)
        return MCPServerTestResult(status="error", message=str(e))
