"""SQLite 用户仓储：持久化登录账号、角色与聊天额度配置。"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import aiosqlite


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SqliteUserRepository:
    """基于 aiosqlite 的用户仓储，复用会话数据库。"""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    async def _prepare(self, db: aiosqlite.Connection) -> None:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode = WAL")
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id                  TEXT PRIMARY KEY,
                username            TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash       TEXT NOT NULL,
                role                TEXT NOT NULL DEFAULT 'user',
                daily_round_limit   INTEGER NOT NULL DEFAULT 3,
                unlimited           INTEGER NOT NULL DEFAULT 0,
                enabled             INTEGER NOT NULL DEFAULT 1,
                created_at          TEXT NOT NULL,
                updated_at          TEXT NOT NULL,
                last_login_at       TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_users_username
            ON users(username);
            """
        )
        await db.commit()

    @staticmethod
    def _to_dict(row: aiosqlite.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        result = dict(row)
        result["unlimited"] = bool(result["unlimited"])
        result["enabled"] = bool(result["enabled"])
        return result

    async def create(
        self,
        *,
        username: str,
        password_hash: str,
        role: str = "user",
        daily_round_limit: int = 3,
        unlimited: bool = False,
    ) -> dict[str, Any]:
        """创建用户并返回不含密码哈希的公开字段。"""
        now = _utc_now()
        user_id = str(uuid4())
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            await db.execute(
                """
                INSERT INTO users (
                    id, username, password_hash, role, daily_round_limit,
                    unlimited, enabled, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    user_id,
                    username.strip(),
                    password_hash,
                    role,
                    daily_round_limit,
                    1 if unlimited else 0,
                    now,
                    now,
                ),
            )
            await db.commit()
        user = await self.get_by_id(user_id)
        if user is None:
            raise RuntimeError("用户创建后无法读取")
        return user

    async def get_by_id(self, user_id: str) -> dict[str, Any] | None:
        """按 ID 查询用户，不返回密码哈希。"""
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                """
                SELECT id, username, role, daily_round_limit, unlimited,
                       enabled, created_at, updated_at, last_login_at
                FROM users WHERE id = ?
                """,
                (user_id,),
            )
            return self._to_dict(await cursor.fetchone())

    async def get_auth_record(self, username: str) -> dict[str, Any] | None:
        """按用户名查询登录校验所需字段。"""
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                """
                SELECT id, username, password_hash, role, daily_round_limit,
                       unlimited, enabled, created_at, updated_at, last_login_at
                FROM users WHERE username = ? COLLATE NOCASE
                """,
                (username.strip(),),
            )
            return self._to_dict(await cursor.fetchone())

    async def update_last_login(self, user_id: str) -> None:
        """记录最近一次成功登录时间。"""
        now = _utc_now()
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            await db.execute(
                "UPDATE users SET last_login_at = ?, updated_at = ? WHERE id = ?",
                (now, now, user_id),
            )
            await db.commit()
