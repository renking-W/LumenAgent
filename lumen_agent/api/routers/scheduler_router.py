"""定时任务管理 CRUD 路由。"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from lumen_agent.api.dependency import get_settings
from lumen_agent.config import Settings, resolve_db_path
from lumen_agent.infrastructure.data_base.sqlite_scheduler import (
    SqliteSchedulerRepository,
)
from lumen_agent.infrastructure.scheduler.scheduler_service import (
    SchedulerService,
)

router = APIRouter(prefix="/v1/scheduler", tags=["scheduler"])
_logger = logging.getLogger(__name__)


class UpdatePromptRequest(BaseModel):
    """``PUT /v1/scheduler/jobs/{job_id}/prompt`` 请求体。"""

    prompt: str = Field(..., min_length=1, description="新的任务提示词")


def _get_repo(settings: Settings = Depends(get_settings)) -> SqliteSchedulerRepository:
    """注入调度器仓储。"""
    return SqliteSchedulerRepository(resolve_db_path(settings))


# ── 任务 CRUD ─────────────────────────────────────────────────


@router.get("/jobs")
async def list_jobs(
    repo: SqliteSchedulerRepository = Depends(_get_repo),
) -> dict[str, Any]:
    """列出所有定时任务及下次执行时间。"""
    tasks = await repo.list_tasks()

    # 附上调度器运行状态
    scheduler_jobs = {}
    if SchedulerService.is_running():
        for j in SchedulerService.get_jobs():
            scheduler_jobs[j["id"]] = j

    items = []
    for t in tasks:
        item: dict[str, Any] = {
            "job_id": t["id"],
            "name": t["name"],
            "prompt": t["prompt"],
            "trigger_type": t["trigger_type"],
            "trigger_expr": t["trigger_expr"],
            "enabled": bool(t["enabled"]),
            "created_by": t["created_by"],
            "created_at": t["created_at"],
        }
        sj = scheduler_jobs.get(t["id"])
        if sj:
            item["next_run_time"] = sj["next_run_time"]
            item["pending"] = sj["pending"]
        items.append(item)

    return {"total": len(items), "jobs": items}


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: str,
    repo: SqliteSchedulerRepository = Depends(_get_repo),
) -> dict[str, Any]:
    """查看单个定时任务详情。"""
    task = await repo.get_task(job_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

    # 获取调度器中的运行状态
    extra: dict[str, Any] = {}
    if SchedulerService.is_running():
        for j in SchedulerService.get_jobs():
            if j["id"] == job_id:
                extra["next_run_time"] = j["next_run_time"]
                extra["pending"] = j["pending"]

    return {
        "job_id": task["id"],
        "name": task["name"],
        "prompt": task["prompt"],
        "trigger_type": task["trigger_type"],
        "trigger_expr": task["trigger_expr"],
        "timezone": task["timezone"],
        "enabled": bool(task["enabled"]),
        "created_by": task["created_by"],
        "created_at": task["created_at"],
        "updated_at": task["updated_at"],
        **extra,
    }


@router.post("/jobs", status_code=status.HTTP_201_CREATED)
async def create_job(
    body: dict[str, Any],
    repo: SqliteSchedulerRepository = Depends(_get_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """创建定时任务。

    Request body:
    ```json
    {
        "name": "每日AI简报",
        "prompt": "搜索最新AI行业新闻，整理成简报",
        "trigger_type": "cron",
        "trigger_expr": "0 9 * * *",
        "timezone": "Asia/Shanghai"
    }
    ```
    """
    name = (body.get("name") or "").strip()
    prompt = (body.get("prompt") or "").strip()
    trigger_type = (body.get("trigger_type") or "").strip()
    trigger_expr = (body.get("trigger_expr") or "").strip()
    timezone = (body.get("timezone") or settings.get("SCHEDULER_TIMEZONE", "Asia/Shanghai")).strip()

    if not all([name, prompt, trigger_type, trigger_expr]):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="name、prompt、trigger_type、trigger_expr 不能为空")

    # 生成 ID
    task_id = f"scheduled_{uuid.uuid4().hex[:8]}"

    # 注册到 APScheduler
    if not SchedulerService.is_running():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="调度器未运行")

    try:
        if trigger_type == "cron":
            trigger = SchedulerService.cron_trigger(trigger_expr, timezone=timezone)
        elif trigger_type == "interval":
            trigger = SchedulerService.interval_trigger(int(trigger_expr))
        elif trigger_type == "date":
            trigger = SchedulerService.date_trigger(trigger_expr)
        else:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail=f"不支持的触发器类型: {trigger_type}")

        SchedulerService.add_job(
            func="lumen_agent.infrastructure.scheduler.tasks:execute_scheduled_agent_task",
            trigger=trigger,
            job_id=task_id,
            name=name,
            kwargs={
                "task_id": task_id,
                "session_id": f"__scheduled__{task_id}",
                "task_name": name,
                "prompt": prompt,
                "trigger_type": trigger_type,
            },
            replace_existing=False,
        )
    except Exception as exc:
        _logger.exception("注册调度任务失败")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"注册调度任务失败: {exc}")

    # 持久化
    await repo.add_task({
        "id": task_id,
        "name": name,
        "prompt": prompt,
        "trigger_type": trigger_type,
        "trigger_expr": trigger_expr,
        "timezone": timezone,
        "enabled": True,
        "created_by": "api",
        "session_id": f"__scheduled__{task_id}",
    })

    # ── 创建对应的会话（kind=1 定时任务） ────────────────────
    from lumen_agent.infrastructure.data_base.sqlite_conversation import (
        SqliteConversationRepository,
    )

    conv_repo = SqliteConversationRepository(resolve_db_path(settings))
    await conv_repo.ensure_session(f"__scheduled__{task_id}", kind=1)
    await conv_repo.update_session_title(f"__scheduled__{task_id}", name)

    _logger.info("API 创建定时任务: id=%s name=%s trigger=%s/%s",
                 task_id, name, trigger_type, trigger_expr)

    return {
        "job_id": task_id,
        "name": name,
        "trigger_type": trigger_type,
        "trigger_expr": trigger_expr,
        "message": f"定时任务「{name}」已创建",
    }


@router.delete("/jobs/{job_id}")
async def delete_job(
    job_id: str,
    repo: SqliteSchedulerRepository = Depends(_get_repo),
) -> dict[str, str]:
    """删除定时任务及其执行记录。"""
    task = await repo.get_task(job_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

    if SchedulerService.is_running():
        SchedulerService.remove_job(job_id)

    await repo.delete_task(job_id)
    _logger.info("API 删除定时任务: id=%s", job_id)
    return {"message": f"任务 {job_id} 已删除", "job_id": job_id}


@router.patch("/jobs/{job_id}/pause")
async def pause_job(
    job_id: str,
    repo: SqliteSchedulerRepository = Depends(_get_repo),
) -> dict[str, str]:
    """暂停定时任务。"""
    task = await repo.get_task(job_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

    if SchedulerService.is_running():
        SchedulerService.pause_job(job_id)
    await repo.update_task(job_id, {"enabled": False})
    return {"message": f"任务 {job_id} 已暂停", "job_id": job_id}


@router.patch("/jobs/{job_id}/resume")
async def resume_job(
    job_id: str,
    repo: SqliteSchedulerRepository = Depends(_get_repo),
) -> dict[str, str]:
    """恢复定时任务。"""
    task = await repo.get_task(job_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

    if SchedulerService.is_running():
        SchedulerService.resume_job(job_id)
    await repo.update_task(job_id, {"enabled": True})
    return {"message": f"任务 {job_id} 已恢复", "job_id": job_id}


# ── 执行记录 ─────────────────────────────────────────────────


@router.get("/jobs/{job_id}/executions")
async def list_executions(
    job_id: str,
    repo: SqliteSchedulerRepository = Depends(_get_repo),
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """查看指定任务的执行记录。"""
    task = await repo.get_task(job_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

    records = await repo.list_executions(job_id, limit=limit, offset=offset)
    return {
        "task_id": job_id,
        "total": len(records),
        "executions": records,
    }


@router.put("/jobs/{job_id}/prompt")
async def update_job_prompt(
    job_id: str,
    body: UpdatePromptRequest,
    repo: SqliteSchedulerRepository = Depends(_get_repo),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    """更新定时任务的提示词。同时更新 DB 和调度器中的运行时参数。"""
    task = await repo.get_task(job_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

    prompt = body.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="prompt 不能为空")

    # 1) 更新数据库
    await repo.update_task(job_id, {"prompt": prompt})

    # 2) 如果调度器正在运行，用新 prompt 重新注册任务
    if SchedulerService.is_running():
        try:
            SchedulerService.remove_job(job_id)
        except Exception:
            pass  # 作业可能不存在
        try:
            if task["trigger_type"] == "cron":
                tz = task.get("timezone", settings.get("SCHEDULER_TIMEZONE", "Asia/Shanghai"))
                trigger = SchedulerService.cron_trigger(task["trigger_expr"], timezone=tz)
            elif task["trigger_type"] == "interval":
                trigger = SchedulerService.interval_trigger(int(task["trigger_expr"]))
            elif task["trigger_type"] == "date":
                trigger = SchedulerService.date_trigger(task["trigger_expr"])
            else:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="无效的触发器类型")

            SchedulerService.add_job(
                func="lumen_agent.infrastructure.scheduler.tasks:execute_scheduled_agent_task",
                trigger=trigger,
                job_id=job_id,
                name=task["name"],
                kwargs={
                    "task_id": job_id,
                    "session_id": task.get("session_id", f"__scheduled__{job_id}"),
                    "task_name": task["name"],
                    "prompt": prompt,
                    "trigger_type": task["trigger_type"],
                },
                replace_existing=True,
            )
        except Exception as exc:
            _logger.exception("使用更新后的提示词重新注册调度任务失败")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"重新注册调度任务失败: {exc}",
            )

    _logger.info("已更新定时任务提示词: id=%s", job_id)
    return {"status": "ok", "job_id": job_id, "prompt": prompt}


@router.get("/health")
async def scheduler_health() -> dict[str, Any]:
    """调度器运行状态探针。"""
    return {
        "running": SchedulerService.is_running(),
        "jobs": SchedulerService.get_jobs() if SchedulerService.is_running() else [],
    }
