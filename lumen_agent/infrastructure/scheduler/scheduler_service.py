"""调度器核心：封装 AsyncIOScheduler，提供统一启停与任务管理接口。

持久化策略：
- APScheduler 使用 MemoryJobStore（进程内），服务重启后内存中的 job 会丢失。
- 所有任务元数据保存在 `scheduled_tasks` 表（通过 SqliteSchedulerRepository）。
- 服务启动后调用 ``restore_from_db()`` 从数据库恢复所有已启用的任务。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

_Trigger = CronTrigger | IntervalTrigger | DateTrigger


def _resolve_db_path_for_scheduler(db_path_str: str) -> str:
    """将 config 中的相对路径转为 SQLAlchemy 格式。"""
    from pathlib import Path
    p = Path(db_path_str)
    if not p.is_absolute():
        from lumen_agent.config import _PACKAGE_DIR
        p = _PACKAGE_DIR / p
    p.parent.mkdir(parents=True, exist_ok=True)
    return str(p)


class SchedulerService:
    """APScheduler 统一封装（类方法，进程级单例）。

    职责：
    - 通过 FastAPI lifespan 启动/停止
    - add_job / remove_job / get_jobs / pause_job / resume_job
    - restore_from_db() 启动时从数据库恢复持久化任务
    - 内置 cron / interval / date 三种触发器工厂
    """

    _scheduler: AsyncIOScheduler | None = None

    # ── 生命周期 ────────────────────────────────────────────────

    @classmethod
    async def start(cls, timezone: str = "Asia/Shanghai") -> None:
        """初始化 AsyncIOScheduler（MemoryJobStore）并启动。

        Args:
            timezone: 调度器时区，默认 Asia/Shanghai
        """
        if cls._scheduler is not None and cls._scheduler.running:
            logger.warning("调度器已在运行，跳过重复启动")
            return

        jobstores = {
            "default": MemoryJobStore(),
        }
        cls._scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            timezone=timezone,
            job_defaults={
                "coalesce": True,
                "max_instances": 1,
                "misfire_grace_time": 60,
            },
        )
        cls._scheduler.start()
        logger.info("调度器已启动 (tz=%s)", timezone)

    @classmethod
    async def stop(cls) -> None:
        """优雅关闭调度器。"""
        if cls._scheduler and cls._scheduler.running:
            cls._scheduler.shutdown(wait=False)
            logger.info("调度器已停止")
        cls._scheduler = None

    @classmethod
    def is_running(cls) -> bool:
        return cls._scheduler is not None and cls._scheduler.running

    # ── 启动时从数据库恢复 ───────────────────────────────────────

    @classmethod
    async def restore_from_db(cls) -> int:
        """从 ``scheduled_tasks`` 表读取所有已启用的任务并注册到调度器。

        可在服务启动后调用，使持久化的定时任务恢复运行。
        返回恢复的任务数量。
        """
        from lumen_agent.config import get_settings, resolve_db_path
        from lumen_agent.infrastructure.data_base.sqlite_scheduler import (
            SqliteSchedulerRepository,
        )
        from datetime import datetime, timezone

        settings = get_settings()
        repo = SqliteSchedulerRepository(resolve_db_path(settings))
        tasks = await repo.list_tasks(enabled_only=True)

        restored = 0
        skipped_expired = 0
        now = datetime.now(timezone.utc)
        for task in tasks:
            try:
                # 跳过已过期的一次性任务
                if task["trigger_type"] == "date":
                    from dateutil import parser
                    run_date = parser.parse(task["trigger_expr"]).replace(tzinfo=timezone.utc)
                    if run_date < now:
                        await repo.update_task(task["id"], {"enabled": False})
                        skipped_expired += 1
                        continue

                trigger = cls._build_trigger(
                    task["trigger_type"],
                    task["trigger_expr"],
                    task.get("timezone", "Asia/Shanghai"),
                )
                if trigger is None:
                    logger.warning("跳过任务 %s: 不支持的触发器 %s/%s",
                                   task["id"], task["trigger_type"], task["trigger_expr"])
                    continue

                cls.add_job(
                    func="lumen_agent.infrastructure.scheduler.tasks:execute_scheduled_agent_task",
                    trigger=trigger,
                    job_id=task["id"],
                    name=task["name"],
                    kwargs={
                        "task_id": task["id"],
                        "session_id": task.get("session_id", f"__scheduled__{task['id']}"),
                        "task_name": task["name"],
                        "prompt": task["prompt"],
                        "trigger_type": task["trigger_type"],
                    },
                    replace_existing=True,
                )
                restored += 1
            except Exception:
                logger.exception("恢复任务失败: id=%s name=%s", task["id"], task["name"])

        logger.info("从数据库恢复了 %d 个定时任务", restored)
        return restored

    # ── 系统内置任务（启动时自动注册） ─────────────────────────────

    @classmethod
    def register_system_tasks(cls) -> int:
        """注册系统级内置定时任务（不依赖 DB，每次启动固定注册）。

        所有保留天数从 ``config.json`` 读取，支持运行时修改：
        - ``SCHEDULER_RETAIN_EXECUTION_DAYS``（默认 30）
        - ``SCHEDULER_RETAIN_SESSION_DAYS``（默认 30）
        - ``SCHEDULER_RETAIN_MEMORY_DAYS``（默认 30）
        """
        from lumen_agent.config import get_settings

        settings = get_settings()
        registered = 0

        tz = settings.get("SCHEDULER_TIMEZONE", "Asia/Shanghai")

        # 1. 清理过期执行记录（每天 3:00）
        try:
            cls.add_job(
                func="lumen_agent.infrastructure.scheduler.tasks:cleanup_old_executions",
                trigger=CronTrigger.from_crontab("0 3 * * *", timezone=tz),
                job_id="__system_cleanup_executions",
                name="清理过期执行记录",
                replace_existing=True,
            )
            registered += 1
        except Exception:
            logger.exception("注册系统任务失败: cleanup_executions")

        # 2. 清理不活跃会话（每月 1 日 00:00）
        try:
            cls.add_job(
                func="lumen_agent.infrastructure.scheduler.tasks:cleanup_old_sessions",
                trigger=CronTrigger.from_crontab("0 0 1 * *", timezone=tz),
                job_id="__system_cleanup_sessions",
                name="清理不活跃会话",
                replace_existing=True,
            )
            registered += 1
        except Exception:
            logger.exception("注册系统任务失败: cleanup_sessions")

        # 3. 清理过期记忆文件（每月 1 日 00:00）
        try:
            cls.add_job(
                func="lumen_agent.infrastructure.scheduler.tasks:cleanup_old_memory_files",
                trigger=CronTrigger.from_crontab("0 0 1 * *", timezone=tz),
                job_id="__system_cleanup_memory_files",
                name="清理过期记忆文件",
                replace_existing=True,
            )
            registered += 1
        except Exception:
            logger.exception("注册系统任务失败: cleanup_memory_files")

        if registered:
            logger.info("已注册 %d 个系统内置任务", registered)
        return registered

    # ── 任务管理 ────────────────────────────────────────────────

    @classmethod
    def add_job(
        cls,
        func: str,
        trigger: _Trigger,
        *,
        job_id: str | None = None,
        name: str = "",
        kwargs: dict[str, Any] | None = None,
        replace_existing: bool = False,
        misfire_grace_time: int | None = None,
        max_instances: int | None = None,
    ) -> str:
        """注册一个定时任务。

        Args:
            func: 可调用对象（或 ``module:function`` 路径字符串）
            trigger: CronTrigger / IntervalTrigger / DateTrigger 实例
            job_id: 自定义 ID（不传则自动生成）
            name: 人类可读名称
            kwargs: 传给 func 的关键字参数
            replace_existing: 同 ID 时是否覆盖
            misfire_grace_time: 错过触发后的宽限期（秒）
            max_instances: 最大并发实例数

        Returns:
            任务 ID
        """
        cls._require_running()

        opts: dict[str, Any] = dict(
            trigger=trigger,
            id=job_id,
            name=name or job_id or "",
            kwargs=kwargs or {},
            replace_existing=replace_existing,
        )
        if misfire_grace_time is not None:
            opts["misfire_grace_time"] = misfire_grace_time
        if max_instances is not None:
            opts["max_instances"] = max_instances

        job = cls._scheduler.add_job(func, **opts)
        logger.info("定时任务已注册: id=%s name=%s trigger=%s", job.id, name, trigger)
        return job.id

    @classmethod
    def remove_job(cls, job_id: str) -> bool:
        """删除指定任务。不存在时返回 False 不抛异常。"""
        cls._require_running()
        try:
            cls._scheduler.remove_job(job_id)
            logger.info("定时任务已删除: id=%s", job_id)
            return True
        except Exception:
            logger.warning("删除定时任务失败（可能不存在）: id=%s", job_id)
            return False

    @classmethod
    def pause_job(cls, job_id: str) -> bool:
        """暂停指定任务。"""
        cls._require_running()
        try:
            cls._scheduler.pause_job(job_id)
            logger.info("定时任务已暂停: id=%s", job_id)
            return True
        except Exception:
            logger.warning("暂停定时任务失败: id=%s", job_id)
            return False

    @classmethod
    def resume_job(cls, job_id: str) -> bool:
        """恢复指定任务。"""
        cls._require_running()
        try:
            cls._scheduler.resume_job(job_id)
            logger.info("定时任务已恢复: id=%s", job_id)
            return True
        except Exception:
            logger.warning("恢复定时任务失败: id=%s", job_id)
            return False

    @classmethod
    def get_jobs(cls) -> list[dict[str, Any]]:
        """列出所有已注册任务（元数据，不含序列化对象）。"""
        cls._require_running()
        jobs = cls._scheduler.get_jobs()
        result: list[dict[str, Any]] = []
        for job in jobs:
            result.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": str(job.next_run_time) if job.next_run_time else None,
                "trigger": str(job.trigger),
                "pending": job.pending,
            })
        return result

    # ── 触发器工厂 ──────────────────────────────────────────────

    @staticmethod
    def cron_trigger(
        expr: str,
        timezone: str = "Asia/Shanghai",
    ) -> CronTrigger:
        """cron 表达式触发器，如 ``"0 9 * * *"``（每天 9:00）。"""
        return CronTrigger.from_crontab(expr, timezone=timezone)

    @staticmethod
    def interval_trigger(seconds: int) -> IntervalTrigger:
        """固定间隔触发器。"""
        return IntervalTrigger(seconds=seconds)

    @staticmethod
    def date_trigger(run_date: str) -> DateTrigger:
        """单次日期触发器。``run_date`` 为 ISO 格式如 ``"2026-06-11T14:30:00"``。"""
        from dateutil import parser
        return DateTrigger(run_date=parser.parse(run_date))

    # ── 内部 ────────────────────────────────────────────────────

    @classmethod
    def _require_running(cls) -> None:
        if cls._scheduler is None or not cls._scheduler.running:
            raise RuntimeError("调度器未启动，请先调用 SchedulerService.start()")

    @staticmethod
    def _build_trigger(
        trigger_type: str,
        trigger_expr: str,
        timezone: str = "Asia/Shanghai",
    ) -> _Trigger | None:
        """根据类型和表达式构建触发器对象。"""
        if trigger_type == "cron":
            return CronTrigger.from_crontab(trigger_expr, timezone=timezone)
        elif trigger_type == "interval":
            return IntervalTrigger(seconds=int(trigger_expr))
        elif trigger_type == "date":
            from dateutil import parser
            return DateTrigger(run_date=parser.parse(trigger_expr))
        return None
