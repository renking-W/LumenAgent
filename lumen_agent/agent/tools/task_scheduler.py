"""TaskScheduler 工具：让 Agent 在对话中创建和管理定时任务。"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from lumen_agent.agent.tools.base import BaseTool, ToolResult
from lumen_agent.agent.tools.registry import ToolRegistry
from lumen_agent.config import get_settings, resolve_db_path


@ToolRegistry.register
class TaskScheduler(BaseTool):
    """创建、列出、删除定时任务。支持 cron / interval / date 三种触发器。"""

    _logger = logging.getLogger(__name__)

    name = "task_scheduler"
    description = (
        "创建、列出、删除定时任务。支持三种触发器："
        "cron（如 '每天9点'）、interval（如 '每30分钟'）、date（如 '2小时后'）。"
        "创建时需提供: action=create, trigger_type, 对应的触发器表达式, "
        "task_name（任务名称）, prompt（触发时执行的指令也就是提示词）。"
        "在需要创建定时任务时需要向用户确认任务执行的步骤以及最终需要的产物"
    )
    requires_approval = True
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "list", "delete", "pause", "resume"],
                "description": "操作类型：create 创建任务，list 列出所有任务，delete 删除任务，pause 暂停，resume 恢复。",
            },
            "trigger_type": {
                "type": "string",
                "enum": ["cron", "interval", "date"],
                "description": "触发器类型。action=create 时必填。",
            },
            "trigger_expr": {
                "type": "string",
                "description": (
                    "触发器表达式。action=create 时必填。\n"
                    "- trigger_type=cron: cron 表达式，如 '0 9 * * *'（每天9点）、'*/5 * * * *'（每5分钟）\n"
                    "- trigger_type=interval: 间隔秒数（数字字符串），如 '1800'（30分钟）\n"
                    "- trigger_type=date: ISO 时间，如 '2026-06-11T14:30:00'"
                ),
            },
            "task_name": {
                "type": "string",
                "description": "任务名称。action=create 时必填。例如：'每日AI简报'、'2小时后的提醒'。",
            },
            "prompt": {
                "type": "string",
                "description": "任务触发时要执行的指令。action=create 时必填。这里面需要填写任务执行的详细步骤以及最终产物的格式/内容，例如`1.利用 web_search 搜索 ai 相关信息 2. 将上述信息整理聚合成一个md格式内容 3.将整理后的内容放入 test.md 文件中`。",
            },
            "job_id": {
                "type": "string",
                "description": "要操作的任务 ID。action=delete/pause/resume 时必填。",
            },
            "mcp_names": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "action=create 时可选。要挂载的 MCP Server 名称列表"
                    "（跨 HTTP + stdio 全局唯一）。与 mcp_server_ids 二选一，不可同时传。"
                ),
            },
            "mcp_server_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "action=create 时可选。要挂载的 MCP Server ID 列表。"
                    "与 mcp_names 二选一，不可同时传。"
                ),
            },
        },
        "required": ["action"],
    }

    async def execute(self, params: dict) -> ToolResult:
        action = str(params.get("action", "")).strip()
        if action == "create":
            return await self._create_task(params)
        elif action == "list":
            return await self._list_tasks()
        elif action == "delete":
            return await self._delete_task(params)
        elif action == "pause":
            return await self._pause_task(params)
        elif action == "resume":
            return await self._resume_task(params)
        return ToolResult.error(f"未知操作：{action}，仅支持 create / list / delete / pause / resume。")

    # ── 创建 ────────────────────────────────────────────────────

    async def _create_task(self, params: dict) -> ToolResult:
        trigger_type = str(params.get("trigger_type", "")).strip()
        trigger_expr = str(params.get("trigger_expr", "")).strip()
        task_name = str(params.get("task_name", "")).strip()
        prompt = str(params.get("prompt", "")).strip()

        if not all([trigger_type, trigger_expr, task_name, prompt]):
            return ToolResult.error(
                "创建任务缺少必要参数：trigger_type、trigger_expr、task_name、prompt 均不能为空。"
            )

        # ── 0. 解析 MCP 参数 ────────────────────────────────────
        raw_mcp_names: list[str] | None = params.get("mcp_names") or None
        raw_mcp_ids: list[str] | None = params.get("mcp_server_ids") or None

        if raw_mcp_names and raw_mcp_ids:
            return ToolResult.error("mcp_names 和 mcp_server_ids 只能二选一，不可同时传。")

        mcp_server_ids: list[str] = []
        if raw_mcp_names:
            try:
                from lumen_agent.application.service.mcp.mcp_lookup import resolve_names_to_ids
                settings = get_settings()
                mcp_server_ids = await resolve_names_to_ids(resolve_db_path(settings), raw_mcp_names)
            except ValueError as exc:
                return ToolResult.error(f"MCP 名称解析失败: {exc}")
        elif raw_mcp_ids:
            try:
                from lumen_agent.application.service.mcp.mcp_lookup import validate_ids_exist
                settings = get_settings()
                mcp_server_ids = await validate_ids_exist(resolve_db_path(settings), raw_mcp_ids)
            except ValueError as exc:
                return ToolResult.error(f"MCP ID 校验失败: {exc}")

        # ── 1. 生成 ID ─────────────────────────────────────────
        task_id = f"scheduled_{uuid.uuid4().hex[:8]}"

        # ── 2. 注册到 APScheduler ───────────────────────────────
        try:
            from lumen_agent.infrastructure.scheduler.scheduler_service import (
                SchedulerService,
            )

            if not SchedulerService.is_running():
                return ToolResult.error("调度器未运行，无法创建定时任务。请先确保服务已启动。")

            # 构建触发器
            if trigger_type == "cron":
                trigger = SchedulerService.cron_trigger(trigger_expr)
            elif trigger_type == "interval":
                trigger = SchedulerService.interval_trigger(int(trigger_expr))
            elif trigger_type == "date":
                trigger = SchedulerService.date_trigger(trigger_expr)
            else:
                return ToolResult.error(f"不支持的触发器类型: {trigger_type}")

            SchedulerService.add_job(
                func="lumen_agent.infrastructure.scheduler.tasks:execute_scheduled_agent_task",
                trigger=trigger,
                job_id=task_id,
                name=task_name,
                kwargs={
                    "task_id": task_id,
                    "session_id": f"__scheduled__{task_id}",
                    "task_name": task_name,
                    "prompt": prompt,
                    "mcp_server_ids": mcp_server_ids,
                },
                replace_existing=False,
            )
        except Exception as exc:
            self._logger.exception("注册调度任务失败")
            return ToolResult.error(f"注册调度任务失败: {exc}")

        # ── 3. 持久化到 scheduled_tasks 表 ─────────────────────
        try:
            from lumen_agent.infrastructure.data_base.sqlite_scheduler import (
                SqliteSchedulerRepository,
            )

            settings = get_settings()
            repo = SqliteSchedulerRepository(resolve_db_path(settings))
            await repo.add_task({
                "id": task_id,
                "name": task_name,
                "prompt": prompt,
                "trigger_type": trigger_type,
                "trigger_expr": trigger_expr,
                "timezone": settings.get("SCHEDULER_TIMEZONE", "Asia/Shanghai"),
                "enabled": True,
                "created_by": "agent",
                "session_id": f"__scheduled__{task_id}",
                "mcp_server_ids": mcp_server_ids,
            })
        except Exception as exc:
            self._logger.warning("持久化任务元数据失败（不影响调度）: %s", exc)

        self._logger.info(
            "定时任务已创建: id=%s name=%s trigger=%s/%s",
            task_id, task_name, trigger_type, trigger_expr,
        )

        return ToolResult.success({
            "job_id": task_id,
            "task_name": task_name,
            "trigger_type": trigger_type,
            "trigger_expr": trigger_expr,
            "prompt": prompt,
            "message": f"定时任务「{task_name}」已创建。任务 ID: {task_id}",
        })

    # ── 列表 ────────────────────────────────────────────────────

    async def _list_tasks(self) -> ToolResult:
        try:
            from lumen_agent.infrastructure.data_base.sqlite_scheduler import (
                SqliteSchedulerRepository,
            )
            from lumen_agent.infrastructure.scheduler.scheduler_service import (
                SchedulerService,
            )

            settings = get_settings()
            repo = SqliteSchedulerRepository(resolve_db_path(settings))
            tasks = await repo.list_tasks()

            # 附上调度器运行状态
            scheduler_jobs = {}
            if SchedulerService.is_running():
                for j in SchedulerService.get_jobs():
                    scheduler_jobs[j["id"]] = j

            items = []
            for t in tasks:
                item = {
                    "job_id": t["id"],
                    "name": t["name"],
                    "trigger": f"{t['trigger_type']}({t['trigger_expr']})",
                    "enabled": bool(t["enabled"]),
                    "prompt": t["prompt"],
                    "created_at": t["created_at"],
                }
                if t["id"] in scheduler_jobs:
                    item["next_run_time"] = scheduler_jobs[t["id"]]["next_run_time"]
                items.append(item)

            return ToolResult.success({
                "total": len(items),
                "tasks": items,
            })
        except Exception as exc:
            self._logger.exception("列出定时任务失败")
            return ToolResult.error(f"列出定时任务失败: {exc}")

    # ── 删除 ────────────────────────────────────────────────────

    async def _delete_task(self, params: dict) -> ToolResult:
        job_id = str(params.get("job_id", "")).strip()
        if not job_id:
            return ToolResult.error("job_id 不能为空。")

        try:
            from lumen_agent.infrastructure.scheduler.scheduler_service import (
                SchedulerService,
            )
            from lumen_agent.infrastructure.data_base.sqlite_scheduler import (
                SqliteSchedulerRepository,
            )

            settings = get_settings()
            repo = SqliteSchedulerRepository(resolve_db_path(settings))

            # 从调度器移除
            if SchedulerService.is_running():
                SchedulerService.remove_job(job_id)
            # 从数据库删除
            await repo.delete_task(job_id)

            self._logger.info("定时任务已删除: id=%s", job_id)
            return ToolResult.success({
                "job_id": job_id,
                "message": f"定时任务 {job_id} 已删除。",
            })
        except Exception as exc:
            return ToolResult.error(f"删除定时任务失败: {exc}")

    # ── 暂停 / 恢复 ────────────────────────────────────────────

    async def _pause_task(self, params: dict) -> ToolResult:
        job_id = str(params.get("job_id", "")).strip()
        if not job_id:
            return ToolResult.error("job_id 不能为空。")

        try:
            from lumen_agent.infrastructure.scheduler.scheduler_service import (
                SchedulerService,
            )
            from lumen_agent.infrastructure.data_base.sqlite_scheduler import (
                SqliteSchedulerRepository,
            )

            if SchedulerService.is_running():
                SchedulerService.pause_job(job_id)
            settings = get_settings()
            repo = SqliteSchedulerRepository(resolve_db_path(settings))
            await repo.update_task(job_id, {"enabled": False})
            return ToolResult.success({"job_id": job_id, "message": f"任务 {job_id} 已暂停。"})
        except Exception as exc:
            return ToolResult.error(f"暂停任务失败: {exc}")

    async def _resume_task(self, params: dict) -> ToolResult:
        job_id = str(params.get("job_id", "")).strip()
        if not job_id:
            return ToolResult.error("job_id 不能为空。")

        try:
            from lumen_agent.infrastructure.scheduler.scheduler_service import (
                SchedulerService,
            )
            from lumen_agent.infrastructure.data_base.sqlite_scheduler import (
                SqliteSchedulerRepository,
            )

            if SchedulerService.is_running():
                SchedulerService.resume_job(job_id)
            settings = get_settings()
            repo = SqliteSchedulerRepository(resolve_db_path(settings))
            await repo.update_task(job_id, {"enabled": True})
            return ToolResult.success({"job_id": job_id, "message": f"任务 {job_id} 已恢复。"})
        except Exception as exc:
            return ToolResult.error(f"恢复任务失败: {exc}")
