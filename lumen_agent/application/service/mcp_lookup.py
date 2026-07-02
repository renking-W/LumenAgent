"""MCP 名称/ID 跨表查询工具。

两张表（mcp_servers / mcp_stdio_servers）共用同一 name 命名空间：
- assert_name_available   — 创建/改名前调用，任一表命中即报错
- assert_name_available_exclude — 改名时调用，排除自身 ID
- get_id_by_name          — 按名称查 ID（两表顺序查，先 HTTP 后 stdio）
- resolve_names_to_ids    — 批量 name→ID，任一未找到即 ValueError
- validate_ids_exist      — 批量校验 ID 是否存在（两表合并查），未找到即 ValueError
"""

from __future__ import annotations

import aiosqlite
from pathlib import Path


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
