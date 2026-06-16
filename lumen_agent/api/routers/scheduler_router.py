"""定时任务管理 CRUD 路由：纯 HTTP 编排，全部业务逻辑委托给 scheduler_task_service。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from lumen_agent.api.dependency import get_settings
from lumen_agent.api.schemas.scheduler_dtos import (
    CreateJobRequest,
    CreateJobResponse,
    ExecutionListResponse,
    JobActionResponse,
    SchedulerHealthResponse,
    SchedulerJobItem,
    SchedulerJobList,
    UpdatePromptRequest,
    UpdatePromptResponse,
)
from lumen_agent.application.service.scheduler_task_service import (
    create_job as svc_create_job,
    delete_job as svc_delete_job,
    get_job as svc_get_job,
    list_executions as svc_list_executions,
    list_jobs as svc_list_jobs,
    pause_job as svc_pause_job,
    resume_job as svc_resume_job,
    scheduler_health as svc_scheduler_health,
    update_job_prompt as svc_update_job_prompt,
)
from lumen_agent.config import Settings, resolve_db_path
from lumen_agent.infrastructure.data_base.sqlite_scheduler import (
    SqliteSchedulerRepository,
)

router = APIRouter(prefix="/v1/scheduler", tags=["scheduler"])


def _get_repo(settings: Settings = Depends(get_settings)) -> SqliteSchedulerRepository:
    return SqliteSchedulerRepository(resolve_db_path(settings))


@router.get("/jobs", response_model=SchedulerJobList)
async def list_jobs(
    repo: SqliteSchedulerRepository = Depends(_get_repo),
) -> SchedulerJobList:
    return await svc_list_jobs(repo)


@router.get("/jobs/{job_id}", response_model=SchedulerJobItem)
async def get_job(
    job_id: str,
    repo: SqliteSchedulerRepository = Depends(_get_repo),
) -> SchedulerJobItem:
    result = await svc_get_job(repo, job_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return result


@router.post("/jobs", response_model=CreateJobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    body: CreateJobRequest,
    repo: SqliteSchedulerRepository = Depends(_get_repo),
    settings: Settings = Depends(get_settings),
) -> CreateJobResponse:
    try:
        return await svc_create_job(repo, settings, body)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))


@router.delete("/jobs/{job_id}", response_model=JobActionResponse)
async def delete_job(
    job_id: str,
    repo: SqliteSchedulerRepository = Depends(_get_repo),
) -> JobActionResponse:
    ok = await svc_delete_job(repo, job_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return JobActionResponse(message=f"任务 {job_id} 已删除", job_id=job_id)


@router.patch("/jobs/{job_id}/pause", response_model=JobActionResponse)
async def pause_job(
    job_id: str,
    repo: SqliteSchedulerRepository = Depends(_get_repo),
) -> JobActionResponse:
    ok = await svc_pause_job(repo, job_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return JobActionResponse(message=f"任务 {job_id} 已暂停", job_id=job_id)


@router.patch("/jobs/{job_id}/resume", response_model=JobActionResponse)
async def resume_job(
    job_id: str,
    repo: SqliteSchedulerRepository = Depends(_get_repo),
) -> JobActionResponse:
    ok = await svc_resume_job(repo, job_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return JobActionResponse(message=f"任务 {job_id} 已恢复", job_id=job_id)


@router.get("/jobs/{job_id}/executions", response_model=ExecutionListResponse)
async def list_executions(
    job_id: str,
    repo: SqliteSchedulerRepository = Depends(_get_repo),
    limit: int = 20,
    offset: int = 0,
) -> ExecutionListResponse:
    result = await svc_list_executions(repo, job_id, limit=limit, offset=offset)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return result


@router.put("/jobs/{job_id}/prompt", response_model=UpdatePromptResponse)
async def update_job_prompt(
    job_id: str,
    body: UpdatePromptRequest,
    repo: SqliteSchedulerRepository = Depends(_get_repo),
    settings: Settings = Depends(get_settings),
) -> UpdatePromptResponse:
    try:
        result = await svc_update_job_prompt(repo, settings, job_id, body.prompt.strip())
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return result


@router.get("/health", response_model=SchedulerHealthResponse)
async def scheduler_health() -> SchedulerHealthResponse:
    return svc_scheduler_health()
