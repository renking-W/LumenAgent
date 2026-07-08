"""MCP 工具索引同步：list_tools → search_doc → SQLite + Chroma。

触发时机：应用启动、server 创建/启用/更新备注、测试连接成功；
禁用时清理索引，不做历史回填。
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from lumen_agent.application.service.mcp_tool_rag_service import McpToolRagService
from lumen_agent.config import Settings, get_settings, resolve_db_path
from lumen_agent.infrastructure.data_base.sqlite_mcp import SqliteMCPServerRepository
from lumen_agent.infrastructure.data_base.sqlite_mcp_stdio import SqliteMCPStdioServerRepository
from lumen_agent.infrastructure.data_base.sqlite_mcp_tools import SqliteMCPToolRepository
from lumen_agent.model_adapters.client import get_mcp_manager
from lumen_agent.model_adapters.client.mcp_client import MCPConnection, MCPStdioConnection

logger = logging.getLogger(__name__)


def build_search_doc(
    *,
    server_name: str,
    server_description: str,
    server_kind: str,
    tool_def: dict[str, Any],
) -> str:
    """拼接 MCP 工具检索文档（MVP：server 备注 + MCP 原生字段，不做 LLM 扩写）。"""
    lines = [
        f"[server] {server_name}",
    ]
    note = (server_description or "").strip()
    if note:
        lines.append(f"[server_note] {note}")
    lines.append(f"[server_kind] {server_kind}")
    lines.append(f"[tool] {tool_def.get('name', '')}")
    lines.append(f"[description] {tool_def.get('description', '')}")

    schema = tool_def.get("inputSchema") or {}
    props = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    if props:
        lines.append("[params]")
        for param_name, param_schema in props.items():
            if not isinstance(param_schema, dict):
                continue
            param_type = param_schema.get("type", "any")
            param_desc = param_schema.get("description", "")
            req_label = "required" if param_name in required else "optional"
            lines.append(
                f"- {param_name} ({param_type}, {req_label}): {param_desc}"
            )
    return "\n".join(lines)


def compute_schema_hash(tool_def: dict[str, Any]) -> str:
    """计算 tool schema 指纹，用于检测 MCP 端工具定义是否变更。"""
    payload = json.dumps(
        {
            "name": tool_def.get("name", ""),
            "description": tool_def.get("description", ""),
            "inputSchema": tool_def.get("inputSchema") or {},
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class McpToolSyncService:
    """MCP 工具索引同步服务。"""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        db_path = resolve_db_path(self._settings)
        self._tool_repo = SqliteMCPToolRepository(db_path)
        self._http_repo = SqliteMCPServerRepository(db_path)
        self._stdio_repo = SqliteMCPStdioServerRepository(db_path)
        self._rag = McpToolRagService(self._settings)

    async def sync_server(
        self,
        server_kind: str,
        server_id: str,
        *,
        tool_defs: list[dict[str, Any]] | None = None,
    ) -> int:
        """同步单个 server 的工具索引，返回本次写入 tool 数量。"""
        if server_kind == "http":
            server = await self._http_repo.get(server_id)
        elif server_kind == "stdio":
            server = await self._stdio_repo.get(server_id)
        else:
            raise ValueError(f"未知 server_kind: {server_kind}")

        if server is None:
            logger.warning("sync_server: server %s/%s 不存在", server_kind, server_id)
            return 0

        # 未传入 tool_defs 时，从已连接 manager 或临时连接拉取
        if tool_defs is None:
            tool_defs = await self._fetch_tools(server_kind, server)

        keep_names: set[str] = set()
        batch: list[dict[str, Any]] = []
        for td in tool_defs:
            original_name = td.get("name", "")
            if not original_name:
                continue
            keep_names.add(original_name)
            batch.append({
                "server_kind": server_kind,
                "server_id": server_id,
                "original_name": original_name,
                "description": td.get("description") or "",
                "input_schema": td.get("inputSchema") or {},
                "search_doc": build_search_doc(
                    server_name=server["name"],
                    server_description=server.get("description") or "",
                    server_kind=server_kind,
                    tool_def=td,
                ),
                "schema_hash": compute_schema_hash(td),
            })

        # 1) 写入 SQLite
        saved = await self._tool_repo.upsert_batch(batch)
        # 2) 写入 Chroma（与 SQLite id 对齐）
        for item, saved_item in zip(batch, saved):
            await self._rag.upsert_tool(
                saved_item["id"],
                item["search_doc"],
                {
                    "tool_id": saved_item["id"],
                    "server_kind": server_kind,
                    "server_id": server_id,
                    "original_name": item["original_name"],
                },
            )

        # 3) 删除 list_tools 未返回的旧 tool（DB + 向量）
        stale_ids = await self._tool_repo.delete_stale(
            server_kind, server_id, keep_names
        )
        if stale_ids:
            self._rag.delete_tools(stale_ids)

        logger.info(
            "MCP 工具索引同步完成：%s/%s tools=%s stale=%s",
            server_kind,
            server_id,
            len(saved),
            len(stale_ids),
        )
        return len(saved)

    async def clear_server(self, server_kind: str, server_id: str) -> None:
        """删除 server 下全部 tool 索引（server 禁用或删除时调用）。"""
        ids = await self._tool_repo.delete_by_server(server_kind, server_id)
        self._rag.delete_tools(ids)
        logger.info(
            "MCP 工具索引已清理：%s/%s removed=%s",
            server_kind,
            server_id,
            len(ids),
        )

    async def sync_all_enabled(self) -> int:
        """同步所有 enabled 且已连接的 MCP Server 工具索引。"""
        total = 0
        mgr = get_mcp_manager()
        for server in await self._http_repo.list_enabled():
            if mgr.get_connection(server["id"]) is None:
                logger.warning("HTTP MCP %s 未连接，跳过 sync", server["id"])
                continue
            total += await self.sync_server("http", server["id"])
        for server in await self._stdio_repo.list_enabled():
            if mgr.get_connection(server["id"]) is None:
                logger.warning("stdio MCP %s 未连接，跳过 sync", server["id"])
                continue
            total += await self.sync_server("stdio", server["id"])
        return total

    async def _fetch_tools(
        self, server_kind: str, server: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """从全局 manager 或临时连接获取 list_tools 结果。"""
        mgr = get_mcp_manager()
        conn = mgr.get_connection(server["id"])
        if conn is not None:
            return await conn.list_tools()

        # manager 未连接时（如测试接口），建立临时连接拉取后关闭
        if server_kind == "http":
            temp = MCPConnection(
                server["url"],
                server.get("api_key") or None,
                server.get("transport") or "",
            )
            try:
                await temp.connect()
                return await temp.list_tools()
            finally:
                await temp.close()

        temp = MCPStdioConnection(
            server["command"],
            server.get("args") or [],
            server.get("env") or None,
            server.get("cwd") or None,
        )
        try:
            await temp.connect()
            return await temp.list_tools()
        finally:
            await temp.close()
