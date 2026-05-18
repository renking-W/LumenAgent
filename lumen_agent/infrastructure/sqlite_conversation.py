"""SQLite 会话仓储：``sessions`` / ``messages``，WAL + 每次请求短连接。"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from lumen_agent.domain.messages import blocks_to_json, ensure_blocks
from lumen_agent.domain.ports import SessionFullRow, SessionRow


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
                updated_at TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '会话记录',
                count INTEGER NOT NULL DEFAULT 0,
                summary TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                seq INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '对话消息'
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
        return [{"role": r["role"], "content": ensure_blocks(r["content"])} for r in rows]

    async def append_message(self, session_id: str, role: str, content: Any) -> None:
        """分配下一个 ``seq`` 插入 ``messages``，并刷新 ``sessions.updated_at``。"""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        now = _utc_now()
        content_json = blocks_to_json(ensure_blocks(content))
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
                (session_id, next_seq, role, content_json),
            )
            await db.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, session_id),
            )
            await db.commit()

    async def get_session(self, session_id: str) -> SessionFullRow | None:
        """读取单个会话的完整状态（含摘要、轮次）；不存在返回 ``None``。"""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            # 建表
            await self._prepare(db)
            cursor = await db.execute(
                """
                SELECT id, created_at, updated_at, count, summary
                FROM sessions WHERE id = ?
                """,
                (session_id,),
            )
            row = await cursor.fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "count": int(row["count"]),
            "summary": row["summary"] or "",
        }

    async def list_recent_messages(
        self,
        session_id: str,
        n_messages: int,
    ) -> list[dict[str, Any]]:
        """按 ``seq`` 倒序取最近 ``n_messages`` 条消息，返回时已反转为时间正序。"""
        if n_messages <= 0:
            return []
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                """
                SELECT role, content FROM messages
                WHERE session_id = ?
                ORDER BY seq DESC
                LIMIT ?
                """,
                (session_id, n_messages),
            )
            rows = await cursor.fetchall()
        return [{"role": r["role"], "content": ensure_blocks(r["content"])} for r in reversed(rows)]

    async def update_summary(
        self,
        session_id: str,
        *,
        new_summary: str,
        new_count: int,
    ) -> None:
        """单事务更新 ``sessions.summary`` 与 ``sessions.count``。"""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        now = _utc_now()
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            await db.execute(
                """
                UPDATE sessions
                SET summary = ?, count = ?, updated_at = ?
                WHERE id = ?
                """,
                (new_summary, new_count, now, session_id),
            )
            await db.commit()

    async def increment_round_counter(self, session_id: str) -> int:
        """``count += 1`` 并返回新值；助手消息成功落库后调用。"""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        now = _utc_now()
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            await db.execute(
                """
                UPDATE sessions
                SET count = count + 1, updated_at = ?
                WHERE id = ?
                """,
                (now, session_id),
            )
            cursor = await db.execute(
                "SELECT count FROM sessions WHERE id = ?",
                (session_id,),
            )
            row = await cursor.fetchone()
            await db.commit()
        return int(row["count"]) if row is not None else 0

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
