"""SQLite 会话仓储：``sessions`` / ``messages``，WAL + 每次请求短连接。"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from lumen_agent.domain.ports import SessionRow


def _utc_now() -> str:
    """当前 UTC 时间的 ISO8601 字符串（写入 sessions/messages 时间戳）。"""
    return datetime.now(timezone.utc).isoformat()


class SqliteConversationRepository:
    """基于 aiosqlite 的 ``ConversationRepositoryPort`` 实现（短连接 + WAL）。"""

    def __init__(self, db_path: Path) -> None:
        """``db_path``：SQLite 文件绝对路径。"""
        self._db_path = db_path

    async def _prepare(self, db: aiosqlite.Connection) -> None:
        """打开连接后：Row 工厂、外键、WAL、建表（若不存在）。"""
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA journal_mode = WAL")
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                seq INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                UNIQUE(session_id, seq)
            );
            CREATE INDEX IF NOT EXISTS idx_messages_session_seq
            ON messages(session_id, seq);
            """
        )
        await db.commit()

    async def ensure_session(self, session_id: str) -> None:
        """保证 ``sessions`` 中存在该 ``session_id``（不存在则插入）。"""
        # 确保有文件目录，不存在则创建
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        now = _utc_now()
        # 连接 db
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            # 不存在插入，存在忽略
            await db.execute(
                "INSERT OR IGNORE INTO sessions (id, created_at, updated_at) VALUES (?, ?, ?)",
                (session_id, now, now),
            )
            await db.commit()

    async def list_messages(self, session_id: str) -> list[dict[str, Any]]:
        """查询某会话全部消息，按 ``seq`` 升序。"""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                "SELECT role, content FROM messages WHERE session_id = ? ORDER BY seq ASC",
                (session_id,),
            )
            rows = await cursor.fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    async def append_message(self, session_id: str, role: str, content: str) -> None:
        """分配下一个 ``seq`` 插入 ``messages``，并刷新 ``sessions.updated_at``。"""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        now = _utc_now()
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                "SELECT COALESCE(MAX(seq), -1) + 1 AS next_seq FROM messages WHERE session_id = ?",
                (session_id,),
            )
            row = await cursor.fetchone()
            next_seq = int(row["next_seq"] if row is not None else 0)
            await db.execute(
                """
                INSERT INTO messages (session_id, seq, role, content)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, next_seq, role, content),
            )
            await db.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, session_id),
            )
            await db.commit()

    async def list_sessions(self, *, limit: int = 50, offset: int = 0) -> list[SessionRow]:
        """分页返回会话列表（``updated_at`` 倒序）。"""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                """
                SELECT id, created_at, updated_at FROM sessions
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
            rows = await cursor.fetchall()
        return [
            {
                "id": r["id"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]
