"""定时任务管理服务：任务 CRUD、触发器构建、调度器编排等全部业务逻辑。"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from lumen_agent.api.schemas.scheduler_dtos import (
    CreateJobRequest,
    CreateJobResponse,
    ExecutionListResponse,
    SchedulerHealthResponse,
    SchedulerJobItem,
    SchedulerJobList,
    UpdatePromptResponse,
)
from lumen_agent.config import Settings, resolve_db_path
from lumen_agent.infrastructure.data_base.sqlite_scheduler import (
    SqliteSchedulerRepository,
)
from lumen_agent.infrastructure.scheduler.scheduler_service import (
    SchedulerService,
)

logger = logging.getLogger(__name__)


def _build_trigger(trigger_type: str, trigger_expr: str, timezone: str | None = None) -> Any:
    """根据类型和表达式构建 APScheduler trigger。"""
    if trigger_type == "cron":
        return SchedulerService.cron_trigger(trigger_expr, timezone=timezone)
    if trigger_type == "interval":
        return SchedulerService.interval_trigger(int(trigger_expr))
    if trigger_type == "date":
        return SchedulerService.date_trigger(trigger_expr)
    raise ValueError(f"不支持的触发器类型: {trigger_type}")


def _add_scheduler_state(task: dict) -> dict[str, Any]:
    """附上调度器运行状态（next_run_time、pending）。"""
    extra: dict[str, Any] = {}
    if SchedulerService.is_running():
        for j in SchedulerService.get_jobs():
            if j["id"] == task["id"]:
                extra["next_run_time"] = j["next_run_time"]
                extra["pending"] = j["pending"]
    return extra


async def list_jobs(repo: SqliteSchedulerRepository) -> SchedulerJobList:
    """列出所有定时任务及下次执行时间。"""
    tasks = await repo.list_tasks()
    items: list[SchedulerJobItem] = []
    for t in tasks:
        extra = _add_scheduler_state(t)
        items.append(SchedulerJobItem(
            job_id=t["id"],
            name=t["name"],
            prompt=t["prompt"],
            trigger_type=t["trigger_type"],
            trigger_expr=t["trigger_expr"],
            enabled=bool(t["enabled"]),
            created_by=t["created_by"],
            created_at=t["created_at"],
            next_run_time=extra.get("next_run_time"),
            pending=extra.get("pending"),
        ))
    return SchedulerJobList(total=len(items), jobs=items)


async def get_job(repo: SqliteSchedulerRepository, job_id: str) -> SchedulerJobItem | None:
    """查看单个定时任务详情。未找到返回 None。"""
    task = await repo.get_task(job_id)
    if not task:
        return None
    extra = _add_scheduler_state(task)
    return SchedulerJobItem(
        job_id=task["id"],
        name=task["name"],
        prompt=task["prompt"],
        trigger_type=task["trigger_type"],
        trigger_expr=task["trigger_expr"],
        timezone=task.get("timezone"),
        enabled=bool(task["enabled"]),
        created_by=task["created_by"],
        created_at=task["created_at"],
        updated_at=task.get("updated_at"),
        next_run_time=extra.get("next_run_time"),
        pending=extra.get("pending"),
    )


async def create_job(
    repo: SqliteSchedulerRepository,
    settings: Settings,
    body: CreateJobRequest,
) -> CreateJobResponse:
    """创建定时任务：校验 → 触发器构建 → 注册调度器 → 持久化 DB → 创建会话。

    Raises:
        ValueError: 字段校验失败或不支持的触发器类型。
        RuntimeError: 调度器未运行。
    """
    name = body.name.strip()
    prompt = body.prompt.strip()
    trigger_type = body.trigger_type.strip()
    trigger_expr = body.trigger_expr.strip()
    timezone = (body.timezone or settings.get("SCHEDULER_TIMEZONE", "Asia/Shanghai")).strip()

    if not all([name, prompt, trigger_type, trigger_expr]):
        raise ValueError("name、prompt、trigger_type、trigger_expr 不能为空")

    task_id = f"scheduled_{uuid.uuid4().hex[:8]}"

    if not SchedulerService.is_running():
        raise RuntimeError("调度器未运行")

    try:
        trigger = _build_trigger(trigger_type, trigger_expr, timezone)
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
    except ValueError:
        raise
    except Exception as exc:
        logger.exception("注册调度任务失败")
        raise RuntimeError(f"注册调度任务失败: {exc}") from exc

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

    # 创建对应的会话（kind=1 定时任务）
    from lumen_agent.infrastructure.data_base.sqlite_conversation import (
        SqliteConversationRepository,
    )

    conv_repo = SqliteConversationRepository(resolve_db_path(settings))
    await conv_repo.ensure_session(f"__scheduled__{task_id}", kind=1)
    await conv_repo.update_session_title(f"__scheduled__{task_id}", name)

    logger.info("API 创建定时任务: id=%s name=%s trigger=%s/%s",
                 task_id, name, trigger_type, trigger_expr)

    return CreateJobResponse(
        job_id=task_id,
        name=name,
        trigger_type=trigger_type,
        trigger_expr=trigger_expr,
        message=f"定时任务「{name}」已创建",
    )


async def delete_job(repo: SqliteSchedulerRepository, job_id: str) -> bool:
    """删除定时任务及其执行记录。未找到返回 False。"""
    task = await repo.get_task(job_id)
    if not task:
        return False

    if SchedulerService.is_running():
        SchedulerService.remove_job(job_id)

    await repo.delete_task(job_id)
    logger.info("API 删除定时任务: id=%s", job_id)
    return True


async def pause_job(repo: SqliteSchedulerRepository, job_id: str) -> bool:
    """暂停定时任务。未找到返回 False。"""
    task = await repo.get_task(job_id)
    if not task:
        return False

    if SchedulerService.is_running():
        SchedulerService.pause_job(job_id)
    await repo.update_task(job_id, {"enabled": False})
    return True


async def resume_job(repo: SqliteSchedulerRepository, job_id: str) -> bool:
    """恢复定时任务。未找到返回 False。"""
    task = await repo.get_task(job_id)
    if not task:
        return False

    if SchedulerService.is_running():
        SchedulerService.resume_job(job_id)
    await repo.update_task(job_id, {"enabled": True})
    return True


async def list_executions(
    repo: SqliteSchedulerRepository,
    job_id: str,
    limit: int = 20,
    offset: int = 0,
) -> ExecutionListResponse | None:
    """查看指定任务的执行记录。任务不存在返回 None。"""
    task = await repo.get_task(job_id)
    if not task:
        return None

    records = await repo.list_executions(job_id, limit=limit, offset=offset)
    return ExecutionListResponse(
        task_id=job_id,
        total=len(records),
        executions=records,
    )


async def update_job_prompt(
    repo: SqliteSchedulerRepository,
    settings: Settings,
    job_id: str,
    prompt: str,
) -> UpdatePromptResponse | None:
    """更新定时任务的提示词。同时更新 DB 和调度器中的运行时参数。未找到返回 None。

    Raises:
        ValueError: prompt 为空。
    """
    if not prompt:
        raise ValueError("prompt 不能为空")

    task = await repo.get_task(job_id)
    if not task:
        return None

    # 1) 更新数据库
    await repo.update_task(job_id, {"prompt": prompt})

    # 2) 如果调度器正在运行，用新 prompt 重新注册任务
    if SchedulerService.is_running():
        try:
            SchedulerService.remove_job(job_id)
        except Exception:
            pass  # 作业可能不存在
        try:
            tz = task.get("timezone", settings.get("SCHEDULER_TIMEZONE", "Asia/Shanghai"))
            trigger = _build_trigger(task["trigger_type"], task["trigger_expr"], tz)
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
        except ValueError:
            raise
        except Exception as exc:
            logger.exception("使用更新后的提示词重新注册调度任务失败")
            raise RuntimeError(f"重新注册调度任务失败: {exc}") from exc

    logger.info("已更新定时任务提示词: id=%s", job_id)
    return UpdatePromptResponse(status="ok", job_id=job_id, prompt=prompt)


def scheduler_health() -> SchedulerHealthResponse:
    """调度器运行状态探针。"""
    return SchedulerHealthResponse(
        running=SchedulerService.is_running(),
        jobs=SchedulerService.get_jobs() if SchedulerService.is_running() else [],
    )
