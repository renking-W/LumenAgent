"""SQLite MCP 服务器配置仓储：存储远程 MCP Server 的连接信息，提供增删改查。"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    """生成短 ID 格式：mcp-{seq}，基于时间戳。"""
    import time
    return f"mcp-{int(time.time() * 1000) % 100000:05d}"


class SqliteMCPServerRepository:
    """MCP 服务器配置的 SQLite 仓储（复用 conversation.db）。"""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    async def _prepare(self, db: aiosqlite.Connection) -> None:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA journal_mode = WAL")
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS mcp_servers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                url TEXT NOT NULL,
                api_key TEXT NOT NULL DEFAULT '',
                transport TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        await db.commit()

    # ── 增 ─────────────────────────────────────────────────────

    async def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """新增一条 MCP Server 配置。自动生成 id。"""
        now = _utc_now()
        server_id = _new_id()
        transport = data.get("transport", "") or ""
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            await db.execute(
                """
                INSERT INTO mcp_servers (id, name, url, api_key, transport, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    server_id,
                    data["name"],
                    data["url"],
                    data.get("api_key", "") or "",
                    transport,
                    1 if data.get("enabled", False) else 0,
                    now,
                    now,
                ),
            )
            await db.commit()
        return {
            "id": server_id,
            "name": data["name"],
            "url": data["url"],
            "api_key": data.get("api_key", "") or "",
            "transport": transport,
            "enabled": bool(data.get("enabled", True)),
            "created_at": now,
            "updated_at": now,
        }

    # ── 查 ─────────────────────────────────────────────────────

    async def list_all(self) -> list[dict[str, Any]]:
        """列出所有 MCP Server 配置（按创建时间倒序）。"""
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                "SELECT id, name, url, api_key, transport, enabled, created_at, updated_at "
                "FROM mcp_servers ORDER BY created_at DESC"
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def list_enabled(self) -> list[dict[str, Any]]:
        """列出所有启用的 MCP Server 配置（供启动时全连用）。"""
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                "SELECT id, name, url, api_key, transport, enabled, created_at, updated_at "
                "FROM mcp_servers WHERE enabled = 1 ORDER BY created_at ASC"
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get(self, server_id: str) -> dict[str, Any] | None:
        """查询单个 MCP Server 配置。"""
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                "SELECT id, name, url, api_key, transport, enabled, created_at, updated_at "
                "FROM mcp_servers WHERE id = ?",
                (server_id,),
            )
            row = await cursor.fetchone()
        return dict(row) if row else None

    # ── 改 ─────────────────────────────────────────────────────

    async def update(
        self, server_id: str, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        """更新 MCP Server 配置（只更新提供的字段）。"""
        now = _utc_now()
        fields: list[str] = ["updated_at = ?"]
        values: list[Any] = [now]

        for key in ("name", "url", "api_key", "transport"):
            if key in data:
                fields.append(f"{key} = ?")
                values.append(data[key])

        if "enabled" in data:
            fields.append("enabled = ?")
            values.append(1 if data["enabled"] else 0)

        values.append(server_id)

        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                f"UPDATE mcp_servers SET {', '.join(fields)} WHERE id = ?",
                values,
            )
            await db.commit()
            if cursor.rowcount == 0:
                return None

        return await self.get(server_id)

    async def update_transport(self, server_id: str, transport: str) -> None:
        """回写探测到的 transport 类型（sse / streamable_http）。"""
        now = _utc_now()
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            await db.execute(
                "UPDATE mcp_servers SET transport = ?, updated_at = ? WHERE id = ?",
                (transport, now, server_id),
            )
            await db.commit()

    # ── 删 ─────────────────────────────────────────────────────

    async def delete(self, server_id: str) -> bool:
        """删除 MCP Server 配置。返回是否实际删除。"""
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                "DELETE FROM mcp_servers WHERE id = ?", (server_id,)
            )
            await db.commit()
        return cursor.rowcount > 0
