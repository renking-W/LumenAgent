"""SQLite 仓储：sub_agent_runs + sub_agent_events 两张表。"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

_DDL = """
CREATE TABLE IF NOT EXISTS sub_agent_runs (
    run_id          TEXT PRIMARY KEY,
    parent_session_id TEXT NOT NULL DEFAULT '',
    agent_type      TEXT NOT NULL,
    prompt          TEXT NOT NULL,
    cwd             TEXT NOT NULL DEFAULT '',
    acp_session_id  TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'running',
    created_at      TEXT NOT NULL,
    finished_at     TEXT,
    stop_reason     TEXT,
    summary         TEXT
);
CREATE TABLE IF NOT EXISTS sub_agent_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL,
    seq             INTEGER NOT NULL DEFAULT 0,
    event_type      TEXT NOT NULL,
    payload_json    TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES sub_agent_runs(run_id)
);
CREATE INDEX IF NOT EXISTS idx_sub_agent_events_run_id
    ON sub_agent_events(run_id, seq);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SqliteSubAgentRepository:
    """sub_agent_runs / sub_agent_events 的 SQLite 仓储（共用 conversations.db）。"""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    async def _prepare(self, db: aiosqlite.Connection) -> None:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode = WAL")
        await db.executescript(_DDL)
        await db.commit()

    # ── runs ──────────────────────────────────────────────────────

    async def create_run(self, data: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            await db.execute(
                """INSERT INTO sub_agent_runs
                   (run_id, parent_session_id, agent_type, prompt, cwd, status, created_at)
                   VALUES (?, ?, ?, ?, ?, 'running', ?)""",
                (
                    data["run_id"],
                    data.get("parent_session_id", ""),
                    data["agent_type"],
                    data["prompt"],
                    data.get("cwd", ""),
                    now,
                ),
            )
            await db.commit()
        return await self.get_run(data["run_id"])  # type: ignore[return-value]

    async def update_run(self, run_id: str, updates: dict[str, Any]) -> None:
        fields = []
        values = []
        for key in ("acp_session_id", "status", "finished_at", "stop_reason", "summary"):
            if key in updates:
                fields.append(f"{key} = ?")
                values.append(updates[key])
        if not fields:
            return
        values.append(run_id)
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            await db.execute(
                f"UPDATE sub_agent_runs SET {', '.join(fields)} WHERE run_id = ?",
                values,
            )
            await db.commit()

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                "SELECT * FROM sub_agent_runs WHERE run_id = ?", (run_id,)
            )
            row = await cursor.fetchone()
        return dict(row) if row else None

    async def list_runs(
        self,
        parent_session_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []
        if parent_session_id:
            conditions.append("parent_session_id = ?")
            params.append(parent_session_id)
        if status:
            conditions.append("status = ?")
            params.append(status)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        params.extend([limit, offset])
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                f"SELECT * FROM sub_agent_runs {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                params,
            )
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # ── events ────────────────────────────────────────────────────

    async def append_event(
        self, run_id: str, event_type: str, payload: dict[str, Any]
    ) -> None:
        now = _now()
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                "SELECT COALESCE(MAX(seq), -1) + 1 FROM sub_agent_events WHERE run_id = ?",
                (run_id,),
            )
            row = await cursor.fetchone()
            seq = row[0] if row else 0
            await db.execute(
                """INSERT INTO sub_agent_events (run_id, seq, event_type, payload_json, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (run_id, seq, event_type, json.dumps(payload, ensure_ascii=False), now),
            )
            await db.commit()

    async def list_events(
        self, run_id: str, limit: int = 500, offset: int = 0
    ) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self._db_path) as db:
            await self._prepare(db)
            cursor = await db.execute(
                "SELECT * FROM sub_agent_events WHERE run_id = ? ORDER BY seq LIMIT ? OFFSET ?",
                (run_id, limit, offset),
            )
            rows = await cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["payload"] = json.loads(d.pop("payload_json", "{}"))
            except Exception:
                d["payload"] = {}
            result.append(d)
        return result
