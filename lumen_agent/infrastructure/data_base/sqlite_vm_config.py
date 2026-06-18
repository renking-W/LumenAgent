"""SQLite VM 机器配置仓储：存储远程虚拟机连接信息，提供增删改查。

遵循 SqliteMCPServerRepository 风格（aiosqlite、row_factory、_prepare() 懒建表）。
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SqliteVMConfigRepository:
    """VM 机器配置的 SQLite 仓储（复用 conversation.db）。"""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    async def _prepare(self, db: aiosqlite.Connection) -> None:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA journal_mode = WAL")
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS vm_machines (
                vm_id       TEXT PRIMARY KEY,
                host        TEXT NOT NULL,
                port        INTEGER NOT NULL DEFAULT 22,
                username    TEXT NOT NULL,
                password    TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );
            """
        )
        await db.commit()

    # ── 增 ─────────────────────────────────────────────────────

    async def create(self, data: dict[str, Any]) -> dict[str, Any]:
        """新增一条 VM 配置。vm_id 由调用方传入。"""
        now = _utc_now()
        vm_id = data["vm_id"]
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            # INSERT OR REPLACE：若已存在则覆盖
            await db.execute(
                """
                INSERT OR REPLACE INTO vm_machines (vm_id, host, port, username, password, description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    vm_id,
                    data["host"],
                    int(data.get("port", 22)),
                    data["username"],
                    data["password"],
                    data.get("description", ""),
                    now,
                    now,
                ),
            )
            await db.commit()
        return {
            "vm_id": vm_id,
            "host": data["host"],
            "port": int(data.get("port", 22)),
            "username": data["username"],
            "description": data.get("description", ""),
            "created_at": now,
            "updated_at": now,
        }

    # ── 查 ─────────────────────────────────────────────────────

    async def list_all(self) -> list[dict[str, Any]]:
        """列出所有 VM 配置（按创建时间倒序）。"""
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                "SELECT vm_id, host, port, username, password, description, created_at, updated_at "
                "FROM vm_machines ORDER BY created_at DESC"
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get(self, vm_id: str) -> dict[str, Any] | None:
        """查询单个 VM 配置。"""
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                "SELECT vm_id, host, port, username, password, description, created_at, updated_at "
                "FROM vm_machines WHERE vm_id = ?",
                (vm_id,),
            )
            row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_by_host(self, host: str) -> dict[str, Any] | None:
        """按主机名查询 VM 配置。"""
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                "SELECT vm_id, host, port, username, password, description, created_at, updated_at "
                "FROM vm_machines WHERE host = ?",
                (host,),
            )
            row = await cursor.fetchone()
        return dict(row) if row else None

    # ── 改 ─────────────────────────────────────────────────────

    async def update(
        self, vm_id: str, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        """更新 VM 配置（只更新提供的字段）。"""
        now = _utc_now()
        fields: list[str] = ["updated_at = ?"]
        values: list[Any] = [now]

        for key in ("host", "username", "password", "description"):
            if key in data:
                fields.append(f"{key} = ?")
                values.append(data[key])

        if "port" in data:
            fields.append("port = ?")
            values.append(int(data["port"]))

        values.append(vm_id)

        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                f"UPDATE vm_machines SET {', '.join(fields)} WHERE vm_id = ?",
                values,
            )
            await db.commit()
            if cursor.rowcount == 0:
                return None

        return await self.get(vm_id)

    # ── 删 ─────────────────────────────────────────────────────

    async def delete(self, vm_id: str) -> bool:
        """删除 VM 配置。返回是否实际删除。"""
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                "DELETE FROM vm_machines WHERE vm_id = ?", (vm_id,)
            )
            await db.commit()
        return cursor.rowcount > 0

    # ── 统计 ──────────────────────────────────────────────────

    async def count(self) -> int:
        """统计 VM 配置总数。"""
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute("SELECT COUNT(*) AS cnt FROM vm_machines")
            row = await cursor.fetchone()
        return row["cnt"] if row else 0
