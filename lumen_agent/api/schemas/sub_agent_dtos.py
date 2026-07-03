"""Sub-Agent REST API DTO 定义。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class AdapterInfo(BaseModel):
    name: str
    label: str
    available: bool
    hint: str = ""


class RunSummary(BaseModel):
    run_id: str
    parent_session_id: str
    agent_type: str
    prompt: str
    cwd: str
    acp_session_id: str
    status: str
    created_at: str
    finished_at: str | None = None
    stop_reason: str | None = None
    summary: str | None = None


class EventRecord(BaseModel):
    id: int
    run_id: str
    seq: int
    event_type: str
    payload: dict[str, Any]
    created_at: str


class RunDetail(RunSummary):
    events: list[EventRecord] = []


class StopRunResponse(BaseModel):
    status: str
    run_id: str
