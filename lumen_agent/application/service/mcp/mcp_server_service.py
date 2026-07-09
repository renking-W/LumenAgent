"""MCP Server 管理服务：CRUD 编排、连接管理、测试等全部业务逻辑。

工具索引：创建/启用/更新/测试成功后调用 McpToolSyncService；
description 由 LLM 基于 mcp_tools 自动生成。
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
from lumen_agent.application.service.mcp.mcp_description_service import (
    refresh_server_description_after_sync,
)
from lumen_agent.application.service.mcp.mcp_lookup import (
    assert_name_available,
    assert_name_available_exclude,
)
from lumen_agent.application.service.mcp.mcp_tool_sync_service import McpToolSyncService
from lumen_agent.config import Settings, get_settings, resolve_db_path
from lumen_agent.infrastructure.data_base.sqlite_mcp import SqliteMCPServerRepository
from lumen_agent.model_adapters.base import ModelAdapter
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


async def _sync_http_tools(settings: Settings, server_id: str) -> int:
    """将 HTTP MCP 的 tools 同步到 mcp_tools + Chroma；失败返回 0 不抛。"""
    try:
        return await McpToolSyncService(settings).sync_server("http", server_id)
    except Exception:
        logger.exception("MCP Server %s 工具索引同步失败", server_id)
        return 0


async def _refresh_http_description(
    llm: ModelAdapter | None,
    settings: Settings,
    server: dict[str, Any],
    user_hint: str | None,
) -> None:
    """在 tool sync 之后调用 LLM 生成 description 并写库。"""
    await refresh_server_description_after_sync(
        llm,
        settings,
        server_kind="http",
        server_id=server["id"],
        server_name=server["name"],
        user_hint=user_hint,
    )


async def list_mcp_servers(repo: SqliteMCPServerRepository) -> list[MCPServerResponse]:
    """列出所有已配置的 MCP Server。"""
    servers = await repo.list_all()
    return [_to_response(svr) for svr in servers]


async def create_mcp_server(
    repo: SqliteMCPServerRepository,
    body: MCPServerCreate,
    settings: Settings | None = None,
    llm: ModelAdapter | None = None,
) -> MCPServerResponse:
    """新增 MCP Server 配置。

    若 enabled=True，先用临时连接验证可达性（探测 transport）；
    连接失败直接抛 ValueError，**不写入 DB**。

    用户提交的 description 仅作 user_hint，最终描述由 LLM 在 sync 后生成。
    """
    if settings is None:
        settings = get_settings()
    await assert_name_available(resolve_db_path(settings), body.name)

    # 前端「描述（可选）」→ 生成参考，不落库
    user_hint = (body.description or "").strip() or None
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
    data["description"] = ""  # 占位，稍后由 refresh 写入 LLM 产物
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
            synced = await _sync_http_tools(settings, server["id"])
            logger.info("MCP Server %s 工具索引已同步：%s 个", server["name"], synced)

    # sync 后（或无 tools 时）生成 description；disabled 也会生成短描述
    await _refresh_http_description(llm, settings, server, user_hint)
    updated = await repo.get(server["id"])
    return _to_response(updated or server)


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
    llm: ModelAdapter | None = None,
) -> MCPServerResponse | None:
    """更新 MCP Server 配置，变更 URL/api_key/enabled 时自动重连。

    body.description 若出现在请求中，视为 user_hint 触发重生成，不直接 update 到 DB。
    """
    if settings is None:
        settings = get_settings()
    raw = body.model_dump(exclude_unset=True)
    update_data = {k: v for k, v in raw.items() if v is not None}
    user_hint: str | None = None
    if "description" in raw:
        # 仅当客户端显式传了 description 字段时才当作生成参考
        user_hint = (raw.get("description") or "").strip() or None
        update_data.pop("description", None)

    if not update_data and user_hint is None:
        raise ValueError("没有需要更新的字段")
    if "name" in update_data:
        await assert_name_available_exclude(
            resolve_db_path(settings), update_data["name"], server_id
        )

    if "url" in update_data or "api_key" in update_data:
        update_data["transport"] = ""

    if update_data:
        server = await repo.update(server_id, update_data)
    else:
        server = await repo.get(server_id)
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
        if ok:
            synced = await _sync_http_tools(settings, server_id)
            logger.info("MCP Server %s 工具索引已同步：%s 个", server["name"], synced)
    else:
        await mgr.disconnect(server_id)
        logger.info("MCP Server %s 已断开", server["name"])
        try:
            await McpToolSyncService(settings).clear_server("http", server_id)
        except Exception:
            logger.exception("MCP Server %s 工具索引清理失败", server_id)

    # 每次保存后刷新 description（含仅改 user_hint 的场景）
    await _refresh_http_description(llm, settings, server, user_hint)
    updated = await repo.get(server_id)
    return _to_response(updated or server)


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
        await McpToolSyncService().clear_server("http", server_id)
    except Exception:
        logger.exception("MCP Server %s 工具索引清理失败", server_id)

    logger.info("MCP Server %s 已删除", server_id)
    return True


async def test_mcp_server(
    repo: SqliteMCPServerRepository,
    server_id: str,
    settings: Settings | None = None,
    llm: ModelAdapter | None = None,
) -> MCPServerTestResult | None:
    """测试 MCP Server 连接（临时连接，使用 DB 中已有 transport 加速）。

    测试成功后会 sync tools 并用最新工具列表重生成 description；
    user_hint 置空，避免把已有 LLM 描述当参考造成自我强化。
    """
    if settings is None:
        settings = get_settings()
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
            tools_synced = await McpToolSyncService(settings).sync_server(
                "http", server_id, tool_defs=tools
            )
        except Exception:
            logger.exception("MCP Server %s 测试后工具索引同步失败", server["name"])
        # 测试路径不传 user_hint，仅依据最新 tools 重生成
        await _refresh_http_description(llm, settings, server, user_hint=None)
        logger.info("MCP Server %s 测试通过，%d 个工具", server["name"], len(tools))
        return MCPServerTestResult(
            status="ok",
            tools_count=len(tools),
            tools_synced=tools_synced,
        )
    except Exception as e:
        logger.warning("MCP Server %s 测试失败: %s", server["name"], e)
        return MCPServerTestResult(status="error", message=str(e))
