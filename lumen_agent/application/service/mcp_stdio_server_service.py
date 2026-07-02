"""stdio MCP Server 管理服务：CRUD 编排、连接管理、测试等全部业务逻辑。"""

from __future__ import annotations

import logging

from lumen_agent.api.schemas.mcp_dtos import MCPServerTestResult
from lumen_agent.api.schemas.mcp_stdio_dtos import (
    MCPStdioServerCreate,
    MCPStdioServerResponse,
    MCPStdioServerUpdate,
)
from lumen_agent.application.service.mcp_lookup import (
    assert_name_available,
    assert_name_available_exclude,
)
from lumen_agent.config import Settings, get_settings, resolve_db_path
from lumen_agent.infrastructure.data_base.sqlite_mcp_stdio import (
    SqliteMCPStdioServerRepository,
)
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
        enabled=bool(server["enabled"]),
        created_at=server["created_at"],
        updated_at=server["updated_at"],
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
) -> MCPStdioServerResponse:
    """新增 stdio MCP Server 配置。

    若 enabled=True，先用临时连接验证命令可执行；
    连接失败直接抛 ValueError，**不写入 DB**。
    验证通过后写 DB，再注册到 manager。
    """
    if settings is None:
        settings = get_settings()
    await assert_name_available(resolve_db_path(settings), body.name)

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

    return _to_response(server)


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
) -> MCPStdioServerResponse | None:
    """更新 stdio MCP Server 配置，相关字段变更时自动重连。

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

    server = await repo.update(server_id, update_data)
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
    else:
        await mgr.disconnect(server_id)
        logger.info("stdio MCP Server %s 已断开", server["name"])

    return _to_response(server)


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

    logger.info("stdio MCP Server %s 已删除", server_id)
    return True


async def test_stdio_server(
    repo: SqliteMCPStdioServerRepository,
    server_id: str,
) -> MCPServerTestResult | None:
    """测试 stdio MCP Server 连接（临时连接，不保持）。未找到返回 None。"""
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
        logger.info(
            "stdio MCP Server %s 测试通过，%d 个工具", server["name"], len(tools)
        )
        return MCPServerTestResult(status="ok", tools_count=len(tools))
    except Exception as e:
        logger.warning("stdio MCP Server %s 测试失败: %s", server["name"], e)
        return MCPServerTestResult(status="error", message=str(e))
