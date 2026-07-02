"""SQLite 调度器仓储：``scheduled_tasks`` / ``scheduled_task_executions``。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SqliteSchedulerRepository:
    """基于 aiosqlite 的定时任务持久化（短连接 + WAL）。

    管理两张表:
    - ``scheduled_tasks`` — 任务元数据（name, prompt, trigger, enabled 等）
    - ``scheduled_task_executions`` — 每次触发的执行记录
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    # ── 建表 ────────────────────────────────────────────────────

    async def _prepare(self, db: aiosqlite.Connection) -> None:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode = WAL")
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS scheduled_tasks (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL DEFAULT '',
                prompt TEXT NOT NULL DEFAULT '',
                trigger_type TEXT NOT NULL DEFAULT 'cron',
                trigger_expr TEXT NOT NULL DEFAULT '',
                timezone TEXT NOT NULL DEFAULT 'Asia/Shanghai',
                enabled INTEGER NOT NULL DEFAULT 1,
                created_by TEXT NOT NULL DEFAULT 'agent',
                session_id TEXT NOT NULL DEFAULT '',
                system_prompt TEXT NOT NULL DEFAULT '',
                mcp_server_ids TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS scheduled_task_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL REFERENCES scheduled_tasks(id) ON DELETE CASCADE,
                session_id TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending',
                output TEXT NOT NULL DEFAULT '',
                error_message TEXT NOT NULL DEFAULT '',
                triggered_at TEXT NOT NULL,
                finished_at TEXT NOT NULL DEFAULT ''
            );

            CREATE INDEX IF NOT EXISTS idx_executions_task_id
            ON scheduled_task_executions(task_id);

            CREATE INDEX IF NOT EXISTS idx_executions_triggered_at
            ON scheduled_task_executions(triggered_at);
        """)

    @staticmethod
    def _row_to_dict(row: aiosqlite.Row) -> dict[str, Any]:
        d = dict(row)
        raw = d.get("mcp_server_ids", "[]")
        try:
            d["mcp_server_ids"] = json.loads(raw) if isinstance(raw, str) else raw
        except (ValueError, TypeError):
            d["mcp_server_ids"] = []
        return d

    async def _connect(self) -> aiosqlite.Connection:
        db = await aiosqlite.connect(self._db_path)
        await self._prepare(db)
        return db

    # ── 任务 CRUD ───────────────────────────────────────────────

    async def add_task(self, task: dict[str, Any]) -> str:
        """插入一条定时任务记录，返回 task_id。"""
        now = _utc_now()
        task_id = task.get("id", "")
        db = await self._connect()
        mcp_ids_raw = task.get("mcp_server_ids", [])
        mcp_ids_json = json.dumps(mcp_ids_raw) if isinstance(mcp_ids_raw, list) else mcp_ids_raw
        try:
            await db.execute(
                """
                INSERT INTO scheduled_tasks
                    (id, name, prompt, trigger_type, trigger_expr, timezone,
                     enabled, created_by, session_id, system_prompt, mcp_server_ids,
                     created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    task.get("name", ""),
                    task.get("prompt", ""),
                    task.get("trigger_type", "cron"),
                    task.get("trigger_expr", ""),
                    task.get("timezone", "Asia/Shanghai"),
                    1 if task.get("enabled", True) else 0,
                    task.get("created_by", "agent"),
                    task.get("session_id", ""),
                    task.get("system_prompt", ""),
                    mcp_ids_json,
                    now,
                    now,
                ),
            )
            await db.commit()
            return task_id
        finally:
            await db.close()

    async def update_task(self, task_id: str, updates: dict[str, Any]) -> bool:
        """更新任务字段（只更新传了的字段）。"""
        now = _utc_now()
        allowed = {"name", "prompt", "trigger_type", "trigger_expr",
                    "timezone", "enabled", "system_prompt", "mcp_server_ids"}
        sets = ["updated_at = ?"]
        params: list[Any] = [now]
        for key, value in updates.items():
            if key in allowed:
                sets.append(f"{key} = ?")
                if key == "mcp_server_ids" and isinstance(value, list):
                    params.append(json.dumps(value))
                else:
                    params.append(value)
        if len(sets) == 1:
            return False  # 没有有效字段
        params.append(task_id)
        db = await self._connect()
        try:
            sql = f"UPDATE scheduled_tasks SET {', '.join(sets)} WHERE id = ?"
            await db.execute(sql, params)
            await db.commit()
            return True
        finally:
            await db.close()

    async def delete_task(self, task_id: str) -> bool:
        """删除任务及其全部执行记录。"""
        db = await self._connect()
        try:
            await db.execute("DELETE FROM scheduled_task_executions WHERE task_id = ?", (task_id,))
            await db.execute("DELETE FROM scheduled_tasks WHERE id = ?", (task_id,))
            await db.commit()
            return True
        finally:
            await db.close()

    async def get_task(self, task_id: str) -> dict[str, Any] | None:
        """查询单个任务。"""
        db = await self._connect()
        try:
            cursor = await db.execute("SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,))
            row = await cursor.fetchone()
            return self._row_to_dict(row) if row else None
        finally:
            await db.close()

    async def list_tasks(self, *, enabled_only: bool = False) -> list[dict[str, Any]]:
        """列出所有定时任务。"""
        db = await self._connect()
        try:
            if enabled_only:
                cursor = await db.execute(
                    "SELECT * FROM scheduled_tasks WHERE enabled = 1 ORDER BY created_at DESC",
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM scheduled_tasks ORDER BY created_at DESC",
                )
            rows = await cursor.fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            await db.close()

    # ── 执行记录 ────────────────────────────────────────────────

    async def add_execution(
        self,
        task_id: str,
        session_id: str = "",
        status: str = "pending",
        output: str = "",
    ) -> int:
        """插入一条执行记录，返回记录 ID。"""
        now = _utc_now()
        db = await self._connect()
        try:
            cursor = await db.execute(
                """
                INSERT INTO scheduled_task_executions
                    (task_id, session_id, status, output, triggered_at, finished_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (task_id, session_id, status, output, now, now),
            )
            await db.commit()
            return cursor.lastrowid or 0
        finally:
            await db.close()

    async def list_executions(
        self,
        task_id: str,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """查询指定任务的执行记录。"""
        db = await self._connect()
        try:
            cursor = await db.execute(
                """
                SELECT * FROM scheduled_task_executions
                WHERE task_id = ?
                ORDER BY triggered_at DESC
                LIMIT ? OFFSET ?
                """,
                (task_id, limit, offset),
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        finally:
            await db.close()

    async def delete_old_executions(self, days: int = 30) -> int:
        """清理指定天数前的执行记录。返回删除条数。"""
        from datetime import timedelta
        threshold = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        db = await self._connect()
        try:
            cursor = await db.execute(
                "DELETE FROM scheduled_task_executions WHERE triggered_at < ?",
                (threshold,),
            )
            await db.commit()
            return cursor.rowcount
        finally:
            await db.close()
