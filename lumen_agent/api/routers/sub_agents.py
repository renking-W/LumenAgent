"""Sub-Agent REST 路由：/v1/sub-agents/*"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from lumen_agent.api.schemas.sub_agent_dtos import (
    AdapterInfo,
    EventRecord,
    RunDetail,
    RunSummary,
    StopRunResponse,
)
from lumen_agent.config import get_settings, resolve_db_path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/sub-agents", tags=["sub-agents"])


# ── 适配器列表 ────────────────────────────────────────────────────

@router.get("/adapters", response_model=list[AdapterInfo])
async def list_adapters():
    """列出所有已注册的 sub-agent 适配器及可用性状态。"""
    from lumen_agent.sub_agents.registry import SubAgentRegistry
    return SubAgentRegistry.list_available()


# ── Runs ──────────────────────────────────────────────────────────

@router.get("/runs", response_model=list[RunSummary])
async def list_runs(
    session_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """分页列出历史 runs。可按 parent_session_id 和 status 过滤。"""
    from lumen_agent.infrastructure.data_base.sqlite_sub_agent import SqliteSubAgentRepository
    repo = SqliteSubAgentRepository(resolve_db_path(get_settings()))
    runs = await repo.list_runs(
        parent_session_id=session_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return runs


@router.get("/runs/{run_id}", response_model=RunDetail)
async def get_run(run_id: str):
    """获取单个 run 的详情（含事件列表）。"""
    from lumen_agent.infrastructure.data_base.sqlite_sub_agent import SqliteSubAgentRepository
    repo = SqliteSubAgentRepository(resolve_db_path(get_settings()))
    run = await repo.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} 不存在")
    events = await repo.list_events(run_id, limit=500)
    run["events"] = events
    return run


@router.post("/runs/{run_id}/stop", response_model=StopRunResponse)
async def stop_run(run_id: str):
    """手动终止指定 run。"""
    from lumen_agent.application.service.sub_agent_service import get_sub_agent_service
    service = get_sub_agent_service()
    await service.stop_run(run_id)
    return StopRunResponse(status="stopped", run_id=run_id)
