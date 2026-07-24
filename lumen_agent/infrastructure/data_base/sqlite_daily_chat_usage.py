"""SQLite 每日对话用量仓储：原子预占和退还普通用户额度。"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import aiosqlite


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SqliteDailyChatUsageRepository:
    """使用短连接和 ``BEGIN IMMEDIATE`` 串行化同一时刻的额度竞争。"""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    async def _prepare(self, db: aiosqlite.Connection) -> None:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode = WAL")
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS daily_chat_usage (
                usage_date  TEXT NOT NULL,
                user_id     TEXT NOT NULL,
                used_rounds INTEGER NOT NULL DEFAULT 0,
                updated_at  TEXT NOT NULL,
                PRIMARY KEY (usage_date, user_id)
            );
            CREATE INDEX IF NOT EXISTS idx_daily_chat_usage_user
            ON daily_chat_usage(user_id, usage_date);
            """
        )
        await db.commit()

    async def reserve(
        self,
        *,
        usage_date: str,
        user_id: str,
        limit: int,
    ) -> int | None:
        """原子增加一次用量；达到上限时返回 ``None``。"""
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            await db.execute("BEGIN IMMEDIATE")
            try:
                cursor = await db.execute(
                    """
                    SELECT used_rounds FROM daily_chat_usage
                    WHERE usage_date = ? AND user_id = ?
                    """,
                    (usage_date, user_id),
                )
                row = await cursor.fetchone()
                used_rounds = int(row["used_rounds"]) if row else 0
                if used_rounds >= limit:
                    await db.rollback()
                    return None

                next_used = used_rounds + 1
                now = _utc_now()
                await db.execute(
                    """
                    INSERT INTO daily_chat_usage (
                        usage_date, user_id, used_rounds, updated_at
                    ) VALUES (?, ?, ?, ?)
                    ON CONFLICT(usage_date, user_id) DO UPDATE SET
                        used_rounds = excluded.used_rounds,
                        updated_at = excluded.updated_at
                    """,
                    (usage_date, user_id, next_used, now),
                )
                await db.commit()
                return next_used
            except Exception:
                await db.rollback()
                raise

    async def release(self, *, usage_date: str, user_id: str) -> None:
        """Run未创建成功时退还一次预占额度；无记录时保持幂等。"""
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            await db.execute("BEGIN IMMEDIATE")
            try:
                await db.execute(
                    """
                    UPDATE daily_chat_usage
                    SET used_rounds = MAX(used_rounds - 1, 0), updated_at = ?
                    WHERE usage_date = ? AND user_id = ?
                    """,
                    (_utc_now(), usage_date, user_id),
                )
                await db.execute(
                    """
                    DELETE FROM daily_chat_usage
                    WHERE usage_date = ? AND user_id = ? AND used_rounds = 0
                    """,
                    (usage_date, user_id),
                )
                await db.commit()
            except Exception:
                await db.rollback()
                raise
