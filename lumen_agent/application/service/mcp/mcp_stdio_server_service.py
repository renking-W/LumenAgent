"""stdio MCP Server 管理服务：CRUD 编排、连接管理、测试等全部业务逻辑。

工具索引与 description 生成逻辑同 HTTP 版（见 mcp_server_service）。
"""

from __future__ import annotations

import logging
from typing import Any

from lumen_agent.api.schemas.mcp_dtos import MCPServerTestResult
from lumen_agent.api.schemas.mcp_stdio_dtos import (
    MCPStdioServerCreate,
    MCPStdioServerResponse,
    MCPStdioServerUpdate,
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
from lumen_agent.infrastructure.data_base.sqlite_mcp_stdio import (
    SqliteMCPStdioServerRepository,
)
from lumen_agent.model_adapters.base import ModelAdapter
from lumen_agent.model_adapters.client import get_mcp_manager
from lumen_agent.model_adapters.client.mcp_client import MCPStdioConnection

logger = logging.getLogger(__name__)


def _to_response(server: dict) -> MCPStdioServerResponse:
    return MCPStdioServerResponse(
        id=server["id"],
        name=server["name"],
        command=server["command"],
        args=server.get("args") or [],
        env=server.get("env") or {},
        cwd=server.get("cwd") or "",
        description=server.get("description") or "",
        enabled=bool(server["enabled"]),
        created_at=server["created_at"],
        updated_at=server["updated_at"],
    )


async def _sync_stdio_tools(settings: Settings, server_id: str) -> int:
    """将 stdio MCP 的 tools 同步到 mcp_tools + Chroma；失败返回 0 不抛。"""
    try:
        return await McpToolSyncService(settings).sync_server("stdio", server_id)
    except Exception:
        logger.exception("stdio MCP Server %s 工具索引同步失败", server_id)
        return 0


async def _refresh_stdio_description(
    llm: ModelAdapter | None,
    settings: Settings,
    server: dict[str, Any],
    user_hint: str | None,
) -> None:
    """在 tool sync 之后调用 LLM 生成 description 并写库。"""
    await refresh_server_description_after_sync(
        llm,
        settings,
        server_kind="stdio",
        server_id=server["id"],
        server_name=server["name"],
        user_hint=user_hint,
    )


async def list_stdio_servers(
    repo: SqliteMCPStdioServerRepository,
) -> list[MCPStdioServerResponse]:
    """列出所有已配置的 stdio MCP Server。"""
    servers = await repo.list_all()
    return [_to_response(svr) for svr in servers]


async def create_stdio_server(
    repo: SqliteMCPStdioServerRepository,
    body: MCPStdioServerCreate,
    settings: Settings | None = None,
    llm: ModelAdapter | None = None,
) -> MCPStdioServerResponse:
    """新增 stdio MCP Server 配置。

    用户提交的 description 仅作 user_hint，最终描述由 LLM 在 sync 后生成。
    """
    if settings is None:
        settings = get_settings()
    await assert_name_available(resolve_db_path(settings), body.name)

    user_hint = (body.description or "").strip() or None
    args = body.args or []
    env = body.env or None
    cwd = body.cwd or None

    if body.enabled:
        probe = MCPStdioConnection(body.command, args, env, cwd)
        try:
            await probe.connect()
            await probe.close()
            logger.info("stdio MCP Server %s 预连接成功", body.name)
        except Exception as e:
            logger.warning("stdio MCP Server %s 连接验证失败: %s", body.command, e)
            raise ValueError(f"无法启动 stdio MCP Server：{e}") from e

    data = body.model_dump()
    data["description"] = ""  # 占位，稍后由 refresh 写入 LLM 产物
    if data.get("cwd") is None:
        data["cwd"] = ""
    server = await repo.create(data)
    logger.info("stdio MCP Server 已创建：%s（%s）", server["name"], server["command"])

    if server["enabled"]:
        mgr = get_mcp_manager()
        ok = await mgr.connect_stdio_one(
            server["id"],
            server["command"],
            server.get("args") or [],
            server.get("env") or None,
            server.get("cwd") or None,
        )
        if not ok:
            logger.warning(
                "stdio MCP Server %s 注册到 manager 失败（已保存配置）", server["name"]
            )
        else:
            synced = await _sync_stdio_tools(settings, server["id"])
            logger.info("stdio MCP Server %s 工具索引已同步：%s 个", server["name"], synced)

    await _refresh_stdio_description(llm, settings, server, user_hint)
    updated = await repo.get(server["id"])
    return _to_response(updated or server)


async def get_stdio_server(
    repo: SqliteMCPStdioServerRepository,
    server_id: str,
) -> MCPStdioServerResponse | None:
    """查看单个 stdio MCP Server 配置。未找到返回 None。"""
    server = await repo.get(server_id)
    return _to_response(server) if server else None


async def update_stdio_server(
    repo: SqliteMCPStdioServerRepository,
    server_id: str,
    body: MCPStdioServerUpdate,
    settings: Settings | None = None,
    llm: ModelAdapter | None = None,
) -> MCPStdioServerResponse | None:
    """更新 stdio MCP Server 配置，相关字段变更时自动重连。

    body.description 若出现在请求中，视为 user_hint 触发重生成，不直接 update 到 DB。
    """
    if settings is None:
        settings = get_settings()
    raw = body.model_dump(exclude_unset=True)
    update_data = {k: v for k, v in raw.items() if v is not None}
    user_hint: str | None = None
    if "description" in raw:
        user_hint = (raw.get("description") or "").strip() or None
        update_data.pop("description", None)

    if not update_data and user_hint is None:
        raise ValueError("没有需要更新的字段")
    if "name" in update_data:
        await assert_name_available_exclude(
            resolve_db_path(settings), update_data["name"], server_id
        )

    if update_data:
        server = await repo.update(server_id, update_data)
    else:
        server = await repo.get(server_id)
    if server is None:
        return None

    logger.info("stdio MCP Server %s 配置已更新", server["name"])

    mgr = get_mcp_manager()
    if server["enabled"]:
        await mgr.disconnect(server_id)
        ok = await mgr.connect_stdio_one(
            server_id,
            server["command"],
            server.get("args") or [],
            server.get("env") or None,
            server.get("cwd") or None,
        )
        logger.info("stdio MCP Server %s 重连%s", server["name"], "成功" if ok else "失败")
        if ok:
            synced = await _sync_stdio_tools(settings, server_id)
            logger.info("stdio MCP Server %s 工具索引已同步：%s 个", server["name"], synced)
    else:
        await mgr.disconnect(server_id)
        logger.info("stdio MCP Server %s 已断开", server["name"])
        try:
            await McpToolSyncService(settings).clear_server("stdio", server_id)
        except Exception:
            logger.exception("stdio MCP Server %s 工具索引清理失败", server_id)

    # 每次保存后刷新 description
    await _refresh_stdio_description(llm, settings, server, user_hint)
    updated = await repo.get(server_id)
    return _to_response(updated or server)


async def delete_stdio_server(
    repo: SqliteMCPStdioServerRepository,
    server_id: str,
) -> bool:
    """删除 stdio MCP Server 配置，同时断开连接。未找到返回 False。"""
    mgr = get_mcp_manager()
    await mgr.disconnect(server_id)

    deleted = await repo.delete(server_id)
    if not deleted:
        return False

    try:
        await McpToolSyncService().clear_server("stdio", server_id)
    except Exception:
        logger.exception("stdio MCP Server %s 工具索引清理失败", server_id)

    logger.info("stdio MCP Server %s 已删除", server_id)
    return True


async def test_stdio_server(
    repo: SqliteMCPStdioServerRepository,
    server_id: str,
    settings: Settings | None = None,
    llm: ModelAdapter | None = None,
) -> MCPServerTestResult | None:
    """测试 stdio MCP Server 连接（临时连接，不保持）。未找到返回 None。

    测试成功后会 sync tools 并重生成 description；user_hint 置空。
    """
    if settings is None:
        settings = get_settings()
    server = await repo.get(server_id)
    if server is None:
        return None

    conn = MCPStdioConnection(
        server["command"],
        server.get("args") or [],
        server.get("env") or None,
        server.get("cwd") or None,
    )
    try:
        await conn.connect()
        tools = await conn.list_tools()
        await conn.close()
        tools_synced = 0
        try:
            tools_synced = await McpToolSyncService(settings).sync_server(
                "stdio", server_id, tool_defs=tools
            )
        except Exception:
            logger.exception("stdio MCP Server %s 测试后工具索引同步失败", server["name"])
        # 测试路径不传 user_hint，仅依据最新 tools 重生成
        await _refresh_stdio_description(llm, settings, server, user_hint=None)
        logger.info(
            "stdio MCP Server %s 测试通过，%d 个工具", server["name"], len(tools)
        )
        return MCPServerTestResult(
            status="ok",
            tools_count=len(tools),
            tools_synced=tools_synced,
        )
    except Exception as e:
        logger.warning("stdio MCP Server %s 测试失败: %s", server["name"], e)
        return MCPServerTestResult(status="error", message=str(e))
