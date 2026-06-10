"""定时任务回调：APScheduler 触发时执行的异步函数集合。

所有回调函数签名必须为 ``async def func(**kwargs)``，因为
APScheduler 通过 kwargs 传递参数。
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── 工具 ──────────────────────────────────────────────────────

_DATE_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")


def _get_settings_value(key: str, default: Any = None) -> Any:
    """延迟加载 settings（避免模块级循环导入）。"""
    from lumen_agent.config import get_settings

    return get_settings().get(key, default)


# ── Agent 任务执行 ────────────────────────────────────────────


async def execute_scheduled_agent_task(**kwargs: Any) -> dict[str, Any]:
    """【核心回调】定时触发时运行 Agent 工具循环。

    kwargs 包含（由 task_scheduler 工具创建时传入）:
        - task_id: str
        - session_id: str
        - prompt: str
        - task_name: str
        - trigger_type: str       — "cron" / "interval" / "date"
        - system_prompt: str|None
    """
    task_id = kwargs.get("task_id", "?")
    task_name = kwargs.get("task_name", "")
    prompt = kwargs.get("prompt", "")
    trigger_type = kwargs.get("trigger_type", "")
    session_id = kwargs.get("session_id", f"__scheduled__{task_id}")
    logger.info(
        "[ScheduledTask] 触发执行: task_id=%s name=%s prompt=%.80s",
        task_id, task_name, prompt,
    )

    try:
        from lumen_agent.agent.agent import AgentStreamExecutor
        from lumen_agent.agent.prompts.builder import build_system_prompt
        from lumen_agent.agent.skills import load_skills
        from lumen_agent.agent.tools import init_tools
        from lumen_agent.agent.tools.registry import ToolRegistry
        from lumen_agent.config import get_settings
        from lumen_agent.model_adapters import get_model_adapter

        init_tools()

        settings = get_settings()
        llm = get_model_adapter(settings)
        tools = ToolRegistry.create_all_tools()
        skills = load_skills()
        system_content = build_system_prompt(tools, skills) or None

        messages: list[dict[str, Any]] = []
        if system_content:
            messages.append({"role": "system", "content": system_content})
        messages.append({"role": "user", "content": prompt})

        executor = AgentStreamExecutor(
            adapter=llm,
            tools=tools,
            settings=settings,
        )

        final_text = ""
        async for kind, data in executor.run_stream(messages):
            if kind == "content":
                final_text += data
            elif kind == "done":
                final_text = data
            elif kind == "error":
                logger.error("[ScheduledTask] Agent 执行错误: %s", data)
                return await _save_result(task_id, session_id, "failed", data)

        logger.info(
            "[ScheduledTask] 执行完成: task_id=%s chars=%d",
            task_id, len(final_text),
        )

        return await _save_result(
            task_id, session_id, "completed",
            final_text or "(无输出)",
        )

    except Exception as exc:
        logger.exception("[ScheduledTask] 执行异常: task_id=%s", task_id)
        return await _save_result(task_id, session_id, "failed", str(exc))

    finally:
        # 一次性任务无论成功/失败，触发后自动停用
        if trigger_type == "date":
            await _disable_one_shot_task(task_id)


async def _save_result(
    task_id: str,
    session_id: str,
    status: str,
    output: str,
) -> dict[str, Any]:
    """将执行结果持久化到 scheduled_task_executions 表。"""
    try:
        from lumen_agent.config import get_settings, resolve_db_path
        from lumen_agent.infrastructure.data_base.sqlite_scheduler import (
            SqliteSchedulerRepository,
        )

        settings = get_settings()
        repo = SqliteSchedulerRepository(resolve_db_path(settings))
        await repo.add_execution(
            task_id=task_id,
            session_id=session_id,
            status=status,
            output=output,
        )
    except Exception as exc:
        logger.exception("持久化执行记录失败: task_id=%s", task_id)
        raise

    return {
        "task_id": task_id,
        "session_id": session_id,
        "status": status,
        "triggered_at": datetime.now(timezone.utc).isoformat(),
    }


async def _disable_one_shot_task(task_id: str) -> None:
    """一次性任务触发完成后，将其标记为 disabled（避免重启后再次注册）。"""
    try:
        from lumen_agent.config import get_settings, resolve_db_path
        from lumen_agent.infrastructure.data_base.sqlite_scheduler import (
            SqliteSchedulerRepository,
        )

        settings = get_settings()
        repo = SqliteSchedulerRepository(resolve_db_path(settings))
        await repo.update_task(task_id, {"enabled": False})
        logger.info("一次性任务已自动停用: task_id=%s", task_id)
    except Exception:
        logger.exception("停用一次性任务失败: task_id=%s", task_id)


# ── 系统清理任务 ──────────────────────────────────────────────


async def cleanup_old_executions(**kwargs: Any) -> None:
    """系统任务：清理过期的执行记录（保留天数由配置 ``SCHEDULER_RETAIN_EXECUTION_DAYS`` 控制）。"""
    retain_days = _get_settings_value(
        "SCHEDULER_RETAIN_EXECUTION_DAYS",
        kwargs.get("retain_days", 30),
    )
    from lumen_agent.config import get_settings, resolve_db_path
    from lumen_agent.infrastructure.data_base.sqlite_scheduler import (
        SqliteSchedulerRepository,
    )

    settings = get_settings()
    repo = SqliteSchedulerRepository(resolve_db_path(settings))
    deleted = await repo.delete_old_executions(days=int(retain_days))
    if deleted:
        logger.info("清理了 %d 条过期执行记录（保留 %s 天）", deleted, retain_days)


async def cleanup_old_sessions(**kwargs: Any) -> None:
    """系统任务：清理 N 天未更新的不活跃会话及其消息（每月 1 日 00:00 触发）。

    保留天数由配置 ``SCHEDULER_RETAIN_SESSION_DAYS`` 控制，默认 30 天。
    比对字段: ``sessions.updated_at``。
    """
    retain_days = int(
        _get_settings_value(
            "SCHEDULER_RETAIN_SESSION_DAYS",
            kwargs.get("retain_days", 30),
        )
    )
    try:
        from lumen_agent.config import get_settings, resolve_db_path
        from lumen_agent.infrastructure.data_base.sqlite_conversation import (
            SqliteConversationRepository,
        )

        settings = get_settings()
        repo = SqliteConversationRepository(resolve_db_path(settings))
        deleted = await repo.delete_old_sessions(days=retain_days)
        if deleted:
            logger.info("清理了 %d 个不活跃会话（%s 天未更新）", deleted, retain_days)
        else:
            logger.info("无不活跃会话需清理（保留 %s 天）", retain_days)
    except Exception:
        logger.exception("清理不活跃会话失败")


async def cleanup_old_memory_files(**kwargs: Any) -> None:
    """系统任务：清理 ``work_space/memory/`` 中 N 天前的日记文件（每月 1 日 00:00 触发）。

    保留天数由配置 ``SCHEDULER_RETAIN_MEMORY_DAYS`` 控制，默认 30 天。
    文件名格式: ``YYYY-MM-DD.md``，仅删除匹配此格式的文件。
    """
    retain_days = int(
        _get_settings_value(
            "SCHEDULER_RETAIN_MEMORY_DAYS",
            kwargs.get("retain_days", 30),
        )
    )
    try:
        from lumen_agent.config import get_settings, resolve_workspace_dir

        settings = get_settings()
        memory_dir = resolve_workspace_dir(settings) / "memory"

        if not memory_dir.is_dir():
            logger.info("记忆目录不存在，跳过清理: %s", memory_dir)
            return

        now = datetime.now(timezone.utc).astimezone()
        # 计算截止日期（保留 N 天，之前的删除）
        from datetime import timedelta

        cutoff = now - timedelta(days=retain_days)
        cutoff_date = cutoff.date()

        deleted = 0
        skipped = 0
        for fpath in sorted(memory_dir.iterdir()):
            if not fpath.is_file() or fpath.suffix != ".md":
                continue
            m = _DATE_PATTERN.match(fpath.name)
            if not m:
                skipped += 1
                continue

            try:
                from datetime import date

                file_date = date.fromisoformat(m.group(1))
            except ValueError:
                skipped += 1
                continue

            if file_date < cutoff_date:
                fpath.unlink()
                deleted += 1
                logger.debug("已删除过期记忆文件: %s", fpath.name)

        if deleted:
            logger.info("清理了 %d 个过期记忆文件（保留 %s 天）", deleted, retain_days)
        else:
            logger.info("无过期记忆文件需清理（保留 %s 天）", retain_days)
        if skipped:
            logger.debug("跳过了 %d 个不匹配日期格式的文件", skipped)

    except Exception:
        logger.exception("清理过期记忆文件失败")
