"""SQLite stdio MCP 服务器配置仓储：存储本地 stdio MCP Server 的启动信息，提供增删改查。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    """生成短 ID 格式：stdio-{seq}，基于时间戳。"""
    import time
    return f"stdio-{int(time.time() * 1000) % 100000:05d}"


class SqliteMCPStdioServerRepository:
    """stdio MCP 服务器配置的 SQLite 仓储（复用 conversation.db）。"""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    async def _prepare(self, db: aiosqlite.Connection) -> None:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA journal_mode = WAL")
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS mcp_stdio_servers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                command TEXT NOT NULL,
                args_json TEXT NOT NULL DEFAULT '[]',
                env_json TEXT NOT NULL DEFAULT '{}',
                cwd TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        await db.commit()

    def _row_to_dict(self, row: aiosqlite.Row) -> dict[str, Any]:
        d = dict(row)
        d["args"] = json.loads(d.pop("args_json") or "[]")
        d["env"] = json.loads(d.pop("env_json") or "{}")
        d["enabled"] = bool(d["enabled"])
        return d

    # ── 增 ─────────────────────────────────────────────────────

    async def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """新增一条 stdio MCP Server 配置。自动生成 id。"""
        now = _utc_now()
        server_id = _new_id()
        args_json = json.dumps(data.get("args", []) or [])
        env_json = json.dumps(data.get("env", {}) or {})
        cwd = data.get("cwd", "") or ""
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            await db.execute(
                """
                INSERT INTO mcp_stdio_servers
                    (id, name, command, args_json, env_json, cwd, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    server_id,
                    data["name"],
                    data["command"],
                    args_json,
                    env_json,
                    cwd,
                    1 if data.get("enabled", True) else 0,
                    now,
                    now,
                ),
            )
            await db.commit()
        return {
            "id": server_id,
            "name": data["name"],
            "command": data["command"],
            "args": data.get("args", []) or [],
            "env": data.get("env", {}) or {},
            "cwd": cwd,
            "enabled": bool(data.get("enabled", True)),
            "created_at": now,
            "updated_at": now,
        }

    # ── 查 ─────────────────────────────────────────────────────

    async def list_all(self) -> list[dict[str, Any]]:
        """列出所有 stdio MCP Server 配置（按创建时间倒序）。"""
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                "SELECT id, name, command, args_json, env_json, cwd, enabled, created_at, updated_at "
                "FROM mcp_stdio_servers ORDER BY created_at DESC"
            )
            rows = await cursor.fetchall()
        return [self._row_to_dict(r) for r in rows]

    async def list_enabled(self) -> list[dict[str, Any]]:
        """列出所有启用的 stdio MCP Server 配置（供启动时全连用）。"""
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                "SELECT id, name, command, args_json, env_json, cwd, enabled, created_at, updated_at "
                "FROM mcp_stdio_servers WHERE enabled = 1 ORDER BY created_at ASC"
            )
            rows = await cursor.fetchall()
        return [self._row_to_dict(r) for r in rows]

    async def get(self, server_id: str) -> dict[str, Any] | None:
        """查询单个 stdio MCP Server 配置。"""
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                "SELECT id, name, command, args_json, env_json, cwd, enabled, created_at, updated_at "
                "FROM mcp_stdio_servers WHERE id = ?",
                (server_id,),
            )
            row = await cursor.fetchone()
        return self._row_to_dict(row) if row else None

    # ── 改 ─────────────────────────────────────────────────────

    async def update(
        self, server_id: str, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        """更新 stdio MCP Server 配置（只更新提供的字段）。"""
        now = _utc_now()
        fields: list[str] = ["updated_at = ?"]
        values: list[Any] = [now]

        for key in ("name", "command", "cwd"):
            if key in data:
                fields.append(f"{key} = ?")
                values.append(data[key])

        if "args" in data:
            fields.append("args_json = ?")
            values.append(json.dumps(data["args"] or []))

        if "env" in data:
            fields.append("env_json = ?")
            values.append(json.dumps(data["env"] or {}))

        if "enabled" in data:
            fields.append("enabled = ?")
            values.append(1 if data["enabled"] else 0)

        values.append(server_id)

        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                f"UPDATE mcp_stdio_servers SET {', '.join(fields)} WHERE id = ?",
                values,
            )
            await db.commit()
            if cursor.rowcount == 0:
                return None

        return await self.get(server_id)

    # ── 删 ─────────────────────────────────────────────────────

    async def delete(self, server_id: str) -> bool:
        """删除 stdio MCP Server 配置。返回是否实际删除。"""
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                "DELETE FROM mcp_stdio_servers WHERE id = ?", (server_id,)
            )
            await db.commit()
        return cursor.rowcount > 0
