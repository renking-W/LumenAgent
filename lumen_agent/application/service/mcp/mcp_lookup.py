"""MCP 名称/ID 跨表查询工具。

两张表（mcp_servers / mcp_stdio_servers）共用同一 name 命名空间：
- assert_name_available   — 创建/改名前调用，任一表命中即报错
- assert_name_available_exclude — 改名时调用，排除自身 ID
- get_id_by_name          — 按名称查 ID（两表顺序查，先 HTTP 后 stdio）
- resolve_names_to_ids    — 批量 name→ID，任一未找到即 ValueError
- validate_ids_exist      — 批量校验 ID 是否存在（两表合并查），未找到即 ValueError
- load_enabled_mcp_servers_for_prompt — 加载已启用 server（含 description），供 Agent prompt
- load_all_mcp_servers    — 合并已启用 ID 与调用方传入 ID
"""

from __future__ import annotations

import aiosqlite
from pathlib import Path

from lumen_agent.application.uitls.dir_guide import DirGuide
from lumen_agent.infrastructure.data_base.sqlite_mcp import SqliteMCPServerRepository
from lumen_agent.infrastructure.data_base.sqlite_mcp_stdio import SqliteMCPStdioServerRepository


async def _fetch_one(db_path: Path, sql: str, params: tuple) -> dict | None:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(sql, params)
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_id_by_name(db_path: Path, name: str) -> str | None:
    """按名称查询 MCP Server ID，HTTP 表优先，找不到再查 stdio 表。"""
    row = await _fetch_one(
        db_path, "SELECT id FROM mcp_servers WHERE name = ?", (name,)
    )
    if row:
        return row["id"]
    row = await _fetch_one(
        db_path, "SELECT id FROM mcp_stdio_servers WHERE name = ?", (name,)
    )
    return row["id"] if row else None


async def assert_name_available(db_path: Path, name: str) -> None:
    """检查名称在两张表中均未被占用，否则抛 ValueError。"""
    existing_id = await get_id_by_name(db_path, name)
    if existing_id is not None:
        raise ValueError(f"MCP 名称「{name}」已被占用（ID: {existing_id}）")


async def assert_name_available_exclude(
    db_path: Path, name: str, exclude_id: str
) -> None:
    """改名时调用：排除自身 ID 后检查名称是否可用。"""
    existing_id = await get_id_by_name(db_path, name)
    if existing_id is not None and existing_id != exclude_id:
        raise ValueError(f"MCP 名称「{name}」已被占用（ID: {existing_id}）")


async def resolve_names_to_ids(db_path: Path, names: list[str]) -> list[str]:
    """将 MCP 名称列表解析为 ID 列表，任一未找到即 ValueError。"""
    ids: list[str] = []
    for name in names:
        server_id = await get_id_by_name(db_path, name)
        if server_id is None:
            raise ValueError(f"找不到名为「{name}」的 MCP Server")
        ids.append(server_id)
    return ids


async def validate_ids_exist(db_path: Path, ids: list[str]) -> list[str]:
    """校验 ID 列表中所有 ID 均存在（两表合并），未命中则 ValueError。"""
    if not ids:
        return []

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        placeholders = ",".join("?" * len(ids))

        cursor = await db.execute(
            f"SELECT id FROM mcp_servers WHERE id IN ({placeholders})", ids
        )
        http_ids = {row["id"] for row in await cursor.fetchall()}

        cursor = await db.execute(
            f"SELECT id FROM mcp_stdio_servers WHERE id IN ({placeholders})", ids
        )
        stdio_ids = {row["id"] for row in await cursor.fetchall()}

    found = http_ids | stdio_ids
    missing = [i for i in ids if i not in found]
    if missing:
        raise ValueError(f"找不到以下 MCP Server ID：{missing}")
    return ids


async def load_enabled_mcp_servers_for_prompt() -> list[dict]:
    """加载全部已启用 MCP Server（含 LLM 生成的 description）。

    返回结构供 build_system_prompt.add_mcp_server_system 与
    mcp_request_context.set_allowed_server_ids 共用。
    """
    db_path = DirGuide.data_dir() / "conversations.db"
    mcp_server_repo = SqliteMCPServerRepository(db_path)
    mcp_stdio_repo = SqliteMCPStdioServerRepository(db_path)
    servers: list[dict] = []
    # HTTP 与 stdio 分表存储，合并为统一列表并标注 kind
    for svr in await mcp_server_repo.list_enabled():
        servers.append({
            "id": svr["id"],
            "name": svr["name"],
            "kind": "http",
            "description": svr.get("description") or "",
            "enabled": True,
        })
    for svr in await mcp_stdio_repo.list_enabled():
        servers.append({
            "id": svr["id"],
            "name": svr["name"],
            "kind": "stdio",
            "description": svr.get("description") or "",
            "enabled": True,
        })
    return servers


async def load_all_mcp_servers(mcp_server_ids: list[str] | None) -> list[str]:
    """加载全部已启用的 MCP Server ID（合并调用方传入的 id）。"""
    servers = await load_enabled_mcp_servers_for_prompt()
    ids = list(mcp_server_ids or [])
    for svr in servers:
        if svr["id"] not in ids:
            ids.append(svr["id"])
    return ids
