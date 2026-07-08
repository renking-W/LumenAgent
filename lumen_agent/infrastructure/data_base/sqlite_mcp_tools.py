"""SQLite MCP 工具索引仓储：存储每个 MCP tool 的 schema 与检索文档。

与 mcp_servers / mcp_stdio_servers 分离：
- SQLite 存完整 input_schema 与 search_doc（供回表与调试）
- Chroma 只存 search_doc 向量（由 McpToolRagService 写入）
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_tool_id() -> str:
    """生成唯一 tool id（批量 sync 时避免毫秒级时间戳碰撞）。"""
    import uuid

    return f"mt-{uuid.uuid4().hex[:12]}"


class SqliteMCPToolRepository:
    """MCP 工具索引 SQLite 仓储（复用 conversation.db）。"""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    async def _prepare(self, db: aiosqlite.Connection) -> None:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA journal_mode = WAL")
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS mcp_tools (
                id TEXT PRIMARY KEY,
                server_kind TEXT NOT NULL,
                server_id TEXT NOT NULL,
                original_name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                input_schema TEXT NOT NULL DEFAULT '{}',
                search_doc TEXT NOT NULL DEFAULT '',
                schema_hash TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(server_kind, server_id, original_name)
            );
            CREATE INDEX IF NOT EXISTS idx_mcp_tools_server
                ON mcp_tools(server_kind, server_id);
            """
        )
        await db.commit()

    def _row_to_dict(self, row: aiosqlite.Row) -> dict[str, Any]:
        """将 DB 行转为 dict，并解析 input_schema JSON。"""
        d = dict(row)
        d["enabled"] = bool(d["enabled"])
        try:
            d["input_schema"] = json.loads(d.get("input_schema") or "{}")
        except json.JSONDecodeError:
            d["input_schema"] = {}
        return d

    # ── 写 ─────────────────────────────────────────────────────

    async def upsert_batch(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """批量 upsert MCP 工具记录，返回写入后的 id 与定位信息。"""
        if not tools:
            return []
        now = _utc_now()
        saved: list[dict[str, Any]] = []
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            for item in tools:
                server_kind = item["server_kind"]
                server_id = item["server_id"]
                original_name = item["original_name"]
                # 按 (server_kind, server_id, original_name) 定位已有记录
                cursor = await db.execute(
                    """
                    SELECT id FROM mcp_tools
                    WHERE server_kind = ? AND server_id = ? AND original_name = ?
                    """,
                    (server_kind, server_id, original_name),
                )
                existing = await cursor.fetchone()
                tool_id = existing["id"] if existing else _new_tool_id()
                input_schema_json = json.dumps(
                    item.get("input_schema") or {}, ensure_ascii=False
                )
                if existing:
                    await db.execute(
                        """
                        UPDATE mcp_tools SET
                            description = ?,
                            input_schema = ?,
                            search_doc = ?,
                            schema_hash = ?,
                            enabled = 1,
                            updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            item.get("description") or "",
                            input_schema_json,
                            item.get("search_doc") or "",
                            item.get("schema_hash") or "",
                            now,
                            tool_id,
                        ),
                    )
                else:
                    await db.execute(
                        """
                        INSERT INTO mcp_tools (
                            id, server_kind, server_id, original_name,
                            description, input_schema, search_doc, schema_hash,
                            enabled, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                        """,
                        (
                            tool_id,
                            server_kind,
                            server_id,
                            original_name,
                            item.get("description") or "",
                            input_schema_json,
                            item.get("search_doc") or "",
                            item.get("schema_hash") or "",
                            now,
                            now,
                        ),
                    )
                saved.append(
                    {
                        "id": tool_id,
                        "server_kind": server_kind,
                        "server_id": server_id,
                        "original_name": original_name,
                    }
                )
            await db.commit()
        return saved

    async def delete_by_server(self, server_kind: str, server_id: str) -> list[str]:
        """删除某 server 下全部 tool，返回被删 tool id 列表（供 Chroma 同步清理）。"""
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                """
                SELECT id FROM mcp_tools
                WHERE server_kind = ? AND server_id = ?
                """,
                (server_kind, server_id),
            )
            rows = await cursor.fetchall()
            ids = [r["id"] for r in rows]
            if ids:
                await db.execute(
                    """
                    DELETE FROM mcp_tools
                    WHERE server_kind = ? AND server_id = ?
                    """,
                    (server_kind, server_id),
                )
                await db.commit()
        return ids

    async def delete_stale(
        self,
        server_kind: str,
        server_id: str,
        keep_original_names: set[str],
    ) -> list[str]:
        """删除本次 sync 未返回的旧 tool（list_tools 中已不存在的工具）。"""
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                """
                SELECT id, original_name FROM mcp_tools
                WHERE server_kind = ? AND server_id = ?
                """,
                (server_kind, server_id),
            )
            rows = await cursor.fetchall()
            stale_ids = [
                r["id"] for r in rows if r["original_name"] not in keep_original_names
            ]
            if stale_ids:
                placeholders = ",".join("?" * len(stale_ids))
                await db.execute(
                    f"DELETE FROM mcp_tools WHERE id IN ({placeholders})",
                    stale_ids,
                )
                await db.commit()
        return stale_ids

    # ── 查 ─────────────────────────────────────────────────────

    async def get(self, tool_id: str) -> dict[str, Any] | None:
        """按主键查询单条 tool 记录。"""
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                "SELECT * FROM mcp_tools WHERE id = ?", (tool_id,)
            )
            row = await cursor.fetchone()
        return self._row_to_dict(row) if row else None

    async def get_by_ids(self, tool_ids: list[str]) -> list[dict[str, Any]]:
        """批量按 id 查询（向量检索命中后回表用）。"""
        if not tool_ids:
            return []
        placeholders = ",".join("?" * len(tool_ids))
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                f"SELECT * FROM mcp_tools WHERE id IN ({placeholders})",
                tool_ids,
            )
            rows = await cursor.fetchall()
        return [self._row_to_dict(r) for r in rows]

    async def list_all(
        self,
        *,
        server_kind: str | None = None,
        server_id: str | None = None,
        server_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """列出已索引 tool，支持 server 维度过滤。"""
        clauses: list[str] = ["enabled = 1"]
        values: list[Any] = []
        if server_kind:
            clauses.append("server_kind = ?")
            values.append(server_kind)
        if server_id:
            clauses.append("server_id = ?")
            values.append(server_id)
        if server_ids is not None:
            if not server_ids:
                return []
            placeholders = ",".join("?" * len(server_ids))
            clauses.append(f"server_id IN ({placeholders})")
            values.extend(server_ids)
        where = " AND ".join(clauses)
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                f"SELECT * FROM mcp_tools WHERE {where} ORDER BY server_id, original_name",
                values,
            )
            rows = await cursor.fetchall()
        return [self._row_to_dict(r) for r in rows]
