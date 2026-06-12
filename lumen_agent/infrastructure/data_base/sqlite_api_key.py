"""SQLite API Key 仓储：持久化密钥的哈希摘要，提供增删查与启停。"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    """生成短 ID：key-{时间戳后5位}。"""
    import time
    return f"key-{int(time.time() * 1000) % 100000:05d}"


class SqliteApiKeyRepository:
    """API Key 的 SQLite 仓储（复用 conversations.db）。"""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    async def _prepare(self, db: aiosqlite.Connection) -> None:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode = WAL")
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS api_keys (
                id          TEXT PRIMARY KEY,
                key_hash    TEXT NOT NULL UNIQUE,
                name        TEXT NOT NULL DEFAULT '',
                enabled     INTEGER NOT NULL DEFAULT 1,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash
            ON api_keys(key_hash);
            """
        )
        await db.commit()

    # ── 增 ────────────────────────────────────────────────────────

    async def create(self, key_hash: str, name: str = "") -> dict[str, Any]:
        """新增一条 API Key 记录。返回元数据（不含原始 Key）。"""
        now = _utc_now()
        key_id = _new_id()
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            await db.execute(
                """
                INSERT INTO api_keys (id, key_hash, name, enabled, created_at, updated_at)
                VALUES (?, ?, ?, 1, ?, ?)
                """,
                (key_id, key_hash, name, now, now),
            )
            await db.commit()
        return {
            "id": key_id,
            "name": name,
            "enabled": True,
            "created_at": now,
            "updated_at": now,
        }

    # ── 查 ────────────────────────────────────────────────────────

    async def get_by_hash(self, key_hash: str) -> dict[str, Any] | None:
        """按哈希查找启用的 Key。返回记录或 None。"""
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                "SELECT id, name, enabled, created_at, updated_at "
                "FROM api_keys WHERE key_hash = ? AND enabled = 1",
                (key_hash,),
            )
            row = await cursor.fetchone()
        return dict(row) if row else None

    async def get(self, key_id: str) -> dict[str, Any] | None:
        """按 ID 查询 Key（返回元数据，不含 hash）。"""
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                "SELECT id, name, enabled, created_at, updated_at "
                "FROM api_keys WHERE id = ?",
                (key_id,),
            )
            row = await cursor.fetchone()
        return dict(row) if row else None

    async def list_all(self) -> list[dict[str, Any]]:
        """列出所有 API Key（不含 hash，不含原始 Key）。"""
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                "SELECT id, name, enabled, created_at, updated_at "
                "FROM api_keys ORDER BY created_at DESC"
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def count_all(self) -> int:
        """返回 Key 总数。"""
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute("SELECT COUNT(*) AS cnt FROM api_keys")
            row = await cursor.fetchone()
        return row["cnt"] if row else 0

    # ── 改 ────────────────────────────────────────────────────────

    async def set_enabled(self, key_id: str, enabled: bool) -> bool:
        """启用/禁用 Key。返回 Key 是否存在。"""
        now = _utc_now()
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                "UPDATE api_keys SET enabled = ?, updated_at = ? WHERE id = ?",
                (1 if enabled else 0, now, key_id),
            )
            await db.commit()
        return cursor.rowcount > 0

    # ── 删 ────────────────────────────────────────────────────────

    async def delete(self, key_id: str) -> bool:
        """删除 Key。返回是否实际删除。"""
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                "DELETE FROM api_keys WHERE id = ?", (key_id,)
            )
            await db.commit()
        return cursor.rowcount > 0
