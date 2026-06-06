"""SQLite 知识库元数据仓储：文档表 + chunk 表。"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite


def _utc_now() -> str:
    """当前 UTC 时间的 ISO8601 字符串。"""
    return datetime.now(timezone.utc).isoformat()


class SqliteKnowledgeRepository:
    """保存知识文档与切片映射的 SQLite 仓储。"""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def open(self) -> None:
        """打开持久化数据库连接（长连接模式），调用方应在服务启动时调用。"""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self._db_path)
        await self._prepare(self._conn)

    async def close(self) -> None:
        """关闭持久化数据库连接（若已打开）。幂等。"""
        conn = self._conn
        self._conn = None
        if conn is not None:
            await conn.close()

    async def _get_conn(self) -> aiosqlite.Connection:
        """获取数据库连接。

        长连接模式（已调用 open()）：返回持久连接，调用方不应关闭。
        短连接模式（未调用 open()）：创建新连接并 prepare，调用方负责关闭。
        """
        if self._conn is not None:
            return self._conn
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = await aiosqlite.connect(self._db_path)
        await self._prepare(conn)
        return conn

    async def _close_if_shortlived(self, db: aiosqlite.Connection) -> None:
        """短连接模式下关闭连接（长连接模式不操作）。"""
        if self._conn is None:
            await db.close()

    async def _prepare(self, db: aiosqlite.Connection) -> None:
        """初始化表结构。"""
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA journal_mode = WAL")
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS knowledge_documents (
                knowledge_id TEXT NOT NULL,
                file_name TEXT NOT NULL,
                source_name TEXT NOT NULL,
                source_path TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                chunk_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (knowledge_id, file_name)
            );
            CREATE TABLE IF NOT EXISTS knowledge_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                knowledge_id TEXT NOT NULL,
                file_name TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                start_char INTEGER NOT NULL,
                end_char INTEGER NOT NULL,
                content TEXT NOT NULL,
                content_preview TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (knowledge_id, file_name)
                    REFERENCES knowledge_documents (knowledge_id, file_name)
                    ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_knowledge_id_file_name
                ON knowledge_chunks(knowledge_id, file_name);
            CREATE INDEX IF NOT EXISTS idx_knowledge_documents_status ON knowledge_documents(status);
            """
        )
        await db.commit()

    async def create_or_reset_document(
        self,
        *,
        knowledge_id: str,
        file_name: str,
        source_name: str,
        source_path: str | None,
    ) -> None:
        """创建或重置文档主记录为 pending。"""
        now = _utc_now()
        db = await self._get_conn()
        await db.execute("BEGIN")
        try:
            await db.execute(
                """
                INSERT INTO knowledge_documents
                (knowledge_id, file_name, source_name, source_path, status, chunk_count, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'pending', 0, ?, ?)
                ON CONFLICT(knowledge_id, file_name) DO UPDATE SET
                    source_name=excluded.source_name,
                    source_path=excluded.source_path,
                    status='pending',
                    chunk_count=0,
                    updated_at=excluded.updated_at
                """,
                (knowledge_id, file_name, source_name, source_path or '', now, now),
            )
            await db.execute(
                "DELETE FROM knowledge_chunks WHERE knowledge_id = ? AND file_name = ?",
                (knowledge_id, file_name),
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        finally:
            await self._close_if_shortlived(db)

    async def append_chunks(
        self,
        *,
        knowledge_id: str,
        file_name: str,
        chunks: list[dict[str, Any]],
    ) -> None:
        """写入 chunk 映射并更新 chunk_count。"""
        now = _utc_now()
        db = await self._get_conn()
        await db.execute("BEGIN")
        try:
            for chunk in chunks:
                await db.execute(
                    """
                    INSERT INTO knowledge_chunks
                    (knowledge_id, file_name, chunk_index, start_char, end_char, content, content_preview, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        knowledge_id,
                        file_name,
                        chunk["chunk_index"],
                        chunk["start_char"],
                        chunk["end_char"],
                        chunk["content"],
                        chunk["content_preview"],
                        now,
                    ),
                )
            await db.execute(
                """
                UPDATE knowledge_documents
                SET status = 'ready', chunk_count = ?, updated_at = ?
                WHERE knowledge_id = ? AND file_name = ?
                """,
                (len(chunks), now, knowledge_id, file_name),
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        finally:
            await self._close_if_shortlived(db)

    async def mark_failed(self, knowledge_id: str, file_name: str) -> None:
        """将文档标记为失败。"""
        now = _utc_now()
        db = await self._get_conn()
        await db.execute("BEGIN")
        try:
            await db.execute(
                """
                UPDATE knowledge_documents
                SET status = 'failed', updated_at = ?
                WHERE knowledge_id = ? AND file_name = ?
                """,
                (now, knowledge_id, file_name),
            )
            await db.commit()
        except Exception:
            await db.rollback()
            raise
        finally:
            await self._close_if_shortlived(db)

    async def delete_document(self, knowledge_id: str, file_name: str) -> dict[str, Any] | None:
        """删除某个文档及其切片，返回被删除的文档信息。"""
        db = await self._get_conn()
        await db.execute("BEGIN")
        try:
            cursor = await db.execute(
                """
                SELECT knowledge_id, file_name, source_name, source_path, status, chunk_count, created_at, updated_at
                FROM knowledge_documents WHERE knowledge_id = ? AND file_name = ?
                """,
                (knowledge_id, file_name),
            )
            doc = await cursor.fetchone()
            if doc is None:
                await db.rollback()
                return None
            await db.execute(
                "DELETE FROM knowledge_documents WHERE knowledge_id = ? AND file_name = ?",
                (knowledge_id, file_name),
            )
            await db.commit()
            return dict(doc)
        except Exception:
            await db.rollback()
            raise
        finally:
            await self._close_if_shortlived(db)

    async def list_documents(self) -> list[dict[str, Any]]:
        """列出所有文档。"""
        db = await self._get_conn()
        try:
            cursor = await db.execute(
                """
                SELECT knowledge_id, file_name, source_name, source_path, status, chunk_count, created_at, updated_at
                FROM knowledge_documents
                ORDER BY updated_at DESC
                """
            )
            rows = await cursor.fetchall()
        finally:
            await self._close_if_shortlived(db)
        return [dict(row) for row in rows]

    async def get_document(self, knowledge_id: str, file_name: str) -> dict[str, Any] | None:
        """获取某个文档及其 chunk 详情。"""
        db = await self._get_conn()
        try:
            cursor = await db.execute(
                """
                SELECT knowledge_id, file_name, source_name, source_path, status, chunk_count, created_at, updated_at
                FROM knowledge_documents WHERE knowledge_id = ? AND file_name = ?
                """,
                (knowledge_id, file_name),
            )
            doc = await cursor.fetchone()
            if doc is None:
                return None
            cursor = await db.execute(
                """
                SELECT chunk_index, start_char, end_char, content, content_preview, created_at, file_name
                FROM knowledge_chunks
                WHERE knowledge_id = ? AND file_name = ?
                ORDER BY chunk_index ASC
                """,
                (knowledge_id, file_name),
            )
            chunks = await cursor.fetchall()
        finally:
            await self._close_if_shortlived(db)
        result = dict(doc)
        result["chunks"] = [dict(row) for row in chunks]
        return result
