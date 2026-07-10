"""定时任务管理 DTO。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class UpdatePromptRequest(BaseModel):
    """PUT /v1/scheduler/jobs/{job_id}/prompt 请求体。"""

    prompt: str = Field(..., min_length=1, description="新的任务提示词")


class CreateJobRequest(BaseModel):
    """POST /v1/scheduler/jobs 请求体。"""

    name: str = Field(..., min_length=1, description="任务名称")
    prompt: str = Field(..., min_length=1, description="任务提示词")
    trigger_type: str = Field(..., description="cron / interval / date")
    trigger_expr: str = Field(..., description="cron 表达式、秒数或 ISO 日期")
    timezone: str | None = Field(default=None, description="时区，缺省使用配置")


class SchedulerJobItem(BaseModel):
    """单个定时任务响应项。"""

    job_id: str
    name: str
    prompt: str
    trigger_type: str
    trigger_expr: str
    enabled: bool
    created_by: str
    created_at: str
    next_run_time: str | None = None
    pending: bool | None = None
    timezone: str | None = None
    updated_at: str | None = None


class SchedulerJobList(BaseModel):
    """定时任务列表响应。"""

    total: int
    jobs: list[SchedulerJobItem]


class CreateJobResponse(BaseModel):
    """创建任务响应。"""

    job_id: str
    name: str
    trigger_type: str
    trigger_expr: str
    message: str


class UpdatePromptResponse(BaseModel):
    """更新提示词响应。"""

    status: str = "ok"
    job_id: str
    prompt: str


class JobActionResponse(BaseModel):
    """暂停/恢复/删除操作的统一响应。"""

    message: str
    job_id: str


class ExecutionListResponse(BaseModel):
    """执行记录列表响应。"""

    task_id: str
    total: int
    executions: list[dict[str, Any]]


class SchedulerHealthResponse(BaseModel):
    """调度器健康检查响应。"""

    running: bool
    jobs: list[dict[str, Any]]
