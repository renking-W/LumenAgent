"""后台会话运行管理：生成任务与前端订阅解耦，并支持事件游标补放。"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import uuid4

from lumen_agent.api.schemas.stream_events import StreamEventDispatcher
from lumen_agent.infrastructure.http_pool import StreamHandle

logger = logging.getLogger(__name__)

# ── 类型与运行参数 ──────────────────────────────────────────────
RunStatus = Literal["running", "completed", "interrupted", "failed"]
ConnectCallback = Callable[[StreamHandle], Awaitable[None]]
ProducerFactory = Callable[
    [ConnectCallback],
    AsyncIterator[tuple[str, str | dict | list]],
]

_TERMINAL_STATUSES = {"completed", "interrupted", "failed"}
_COMPLETED_RUN_TTL_SECONDS = 600.0


class ActiveSessionRunError(RuntimeError):
    """同一会话已有活跃生成任务。"""

    def __init__(self, session_id: str, run_id: str) -> None:
        super().__init__(f"session {session_id} already has active run {run_id}")
        self.session_id = session_id
        self.run_id = run_id


class ChatRunNotFoundError(KeyError):
    """指定运行不存在或已过期。"""


# ── 运行状态模型 ────────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class ChatRunEvent:
    """带递增序号的可补放事件；payload 为前端事件 JSON。"""

    seq: int
    payload: str


@dataclass(slots=True)
class ChatRun:
    """单轮生成的任务、上游连接、事件缓冲和终态信息。"""

    run_id: str
    session_id: str
    status: RunStatus = "running"
    events: list[ChatRunEvent] = field(default_factory=list)
    condition: asyncio.Condition = field(default_factory=asyncio.Condition)
    task: asyncio.Task[None] | None = None
    handle: StreamHandle | None = None
    interrupt_requested: bool = False
    created_at: float = field(default_factory=time.monotonic)
    # monotonic 时间仅用于进程内 TTL 判断，不作为业务时间返回前端。
    completed_at: float | None = None

    @property
    def terminal(self) -> bool:
        """当前运行是否已经进入不可恢复的终态。"""
        return self.status in _TERMINAL_STATUSES

    @property
    def last_event_id(self) -> int:
        """返回最后一个已缓存事件的游标；没有事件时返回 0。"""
        return self.events[-1].seq if self.events else 0

    def snapshot(self) -> dict[str, Any]:
        """生成可安全返回给前端的运行状态快照。"""
        return {
            "run_id": self.run_id,
            "session_id": self.session_id,
            "status": self.status,
            "last_event_id": self.last_event_id,
        }


class ChatRunManager:
    """独立持有生成任务；浏览器订阅的建立和断开不改变任务生命周期。"""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._runs: dict[str, ChatRun] = {}
        self._active_by_session: dict[str, str] = {}

    async def start(
        self,
        session_id: str,
        producer_factory: ProducerFactory,
    ) -> ChatRun:
        """为会话启动一轮后台生成；同一会话只允许一个活跃任务。"""
        # 全局锁只保护运行索引；单个运行的事件等待使用自己的 Condition。
        async with self._lock:
            self._cleanup_locked()
            active_id = self._active_by_session.get(session_id)
            if active_id is not None:
                active = self._runs.get(active_id)
                if active is not None and not active.terminal:
                    raise ActiveSessionRunError(session_id, active_id)
                self._active_by_session.pop(session_id, None)

            # 启动新任务时顺便回收超过 TTL 的已完成事件缓冲。
            run = ChatRun(run_id=str(uuid4()), session_id=session_id)
            self._runs[run.run_id] = run
            self._active_by_session[session_id] = run.run_id
            run.task = asyncio.create_task(
                self._execute(run, producer_factory),
                name=f"chat-run:{run.run_id}",
            )
            # Task 由 Manager 持有，不挂靠创建它的 HTTP 请求。
            return run

    async def get(self, run_id: str) -> ChatRun:
        """按 run_id 查询运行。"""
        async with self._lock:
            run = self._runs.get(run_id)
        if run is None:
            raise ChatRunNotFoundError(run_id)
        return run

    async def active_runs(self) -> list[dict[str, Any]]:
        """返回所有会话当前仍在执行的运行快照。"""
        async with self._lock:
            result = []
            for run_id in self._active_by_session.values():
                run = self._runs.get(run_id)
                if run is not None and not run.terminal:
                    result.append(run.snapshot())
            return result

    async def active_for_session(self, session_id: str) -> ChatRun | None:
        """查询某个会话的活跃运行。"""
        async with self._lock:
            run_id = self._active_by_session.get(session_id)
            run = self._runs.get(run_id) if run_id else None
        return run if run is not None and not run.terminal else None

    async def attach_handle(self, run_id: str, handle: StreamHandle) -> None:
        """登记当前模型流连接，供显式中断和任务收尾时关闭。"""
        run = await self.get(run_id)
        if run.interrupt_requested or run.terminal:
            await handle.close()
            return

        old = run.handle
        run.handle = handle
        # Agent 多轮调用会产生多个模型流；新连接接管后关闭上一轮句柄。
        if old is not None and old is not handle:
            await old.close()

    async def interrupt(self, run_id: str) -> bool:
        """显式中断指定运行；订阅断开不会进入此方法。"""
        try:
            run = await self.get(run_id)
        except ChatRunNotFoundError:
            return False
        if run.terminal:
            return False

        run.interrupt_requested = True
        task = run.task
        if task is not None and not task.done():
            # 先取消 owner task，由它在 finally 中关闭连接，避免跨任务收尾。
            task.cancel()
        elif run.handle is not None:
            await run.handle.close()
        return True

    async def interrupt_session(self, session_id: str) -> bool:
        """按 session_id 中断其当前活跃运行，兼容旧中断入口。"""
        run = await self.active_for_session(session_id)
        return await self.interrupt(run.run_id) if run is not None else False

    async def subscribe(
        self,
        run_id: str,
        *,
        after: int = 0,
        heartbeat_seconds: float = 15.0,
    ) -> AsyncIterator[ChatRunEvent | None]:
        """先补放游标后的历史事件，再等待实时事件。

        None 表示 SSE 心跳。关闭该迭代器只会移除订阅者，
        不会取消 Manager 持有的生成任务。
        """
        run = await self.get(run_id)
        cursor = max(0, after)

        while True:
            batch: list[ChatRunEvent] = []
            terminal = False
            heartbeat = False
            async with run.condition:
                batch = [event for event in run.events if event.seq > cursor]
                terminal = run.terminal
                if not batch and not terminal:
                    try:
                        await asyncio.wait_for(
                            run.condition.wait(),
                            timeout=heartbeat_seconds,
                        )
                    except TimeoutError:
                        heartbeat = True

            if heartbeat:
                yield None
                continue
            for event in batch:
                cursor = event.seq
                yield event
            # 每次唤醒都按 seq 重新取差集，天然支持多个独立订阅者。
            if terminal and cursor >= run.last_event_id:
                return

    async def close_all(self) -> None:
        """应用关闭时取消并等待全部活跃运行，避免遗留异步任务。"""
        async with self._lock:
            runs = [
                run
                for run in self._runs.values()
                if not run.terminal and run.task is not None
            ]
            for run in runs:
                run.interrupt_requested = True
                run.task.cancel()
        if runs:
            await asyncio.gather(
                *(run.task for run in runs if run.task is not None),
                return_exceptions=True,
            )

    async def wait(self, run_id: str) -> ChatRun:
        """等待指定运行进入终态，主要供测试和内部协调使用。"""
        run = await self.get(run_id)
        task = run.task
        if task is not None:
            try:
                await task
            except asyncio.CancelledError:
                pass
        return run

    async def publish(
        self,
        run_id: str,
        kind: str,
        data: str | dict | list,
    ) -> None:
        """向指定运行追加外部事件，供审批等旁路操作写入可补放缓冲。"""
        run = await self.get(run_id)
        if not run.terminal:
            await self._publish(run, kind, data)

    async def _execute(
        self,
        run: ChatRun,
        producer_factory: ProducerFactory,
    ) -> None:
        """消费业务事件并写入缓冲；订阅者断开不影响此循环。"""
        saw_done = False

        async def on_connect(handle: StreamHandle) -> None:
            await self.attach_handle(run.run_id, handle)

        try:
            async for kind, data in producer_factory(on_connect):
                if kind == "done":
                    saw_done = True
                await self._publish(run, kind, data)
            if not saw_done:
                # 简单模式没有显式 done 事件，由 Manager 统一补齐。
                await self._publish(run, "done", {})
            run.status = "interrupted" if run.interrupt_requested else "completed"
        except asyncio.CancelledError:
            # 只有显式 interrupt 才标记 interrupted；其他取消视为失败。
            run.status = "interrupted" if run.interrupt_requested else "failed"
            await self._publish(
                run,
                "error",
                "stream_interrupted" if run.interrupt_requested else "chat run cancelled",
            )
        except Exception as exc:
            logger.exception("chat run failed: run=%s session=%s", run.run_id, run.session_id)
            await self._publish(run, "error", str(exc))
            run.status = "failed"
        finally:
            handle = run.handle
            run.handle = None
            if handle is not None:
                await handle.close()
            run.completed_at = time.monotonic()
            async with self._lock:
                if self._active_by_session.get(run.session_id) == run.run_id:
                    self._active_by_session.pop(run.session_id, None)
            async with run.condition:
                run.condition.notify_all()
            # 连接关闭、索引移除和订阅唤醒统一由 owner task 收尾。

    async def _publish(
        self,
        run: ChatRun,
        kind: str,
        data: str | dict | list,
    ) -> None:
        """将事件序列化后追加到有序缓冲，并唤醒全部订阅者。"""
        payload = StreamEventDispatcher.serialize(kind, data)
        async with run.condition:
            event = ChatRunEvent(seq=run.last_event_id + 1, payload=payload)
            run.events.append(event)
            run.condition.notify_all()

    def _cleanup_locked(self) -> None:
        """清理终态超过 TTL 的运行；最终消息仍保存在 SQLite。"""
        cutoff = time.monotonic() - _COMPLETED_RUN_TTL_SECONDS
        expired = [
            run_id
            for run_id, run in self._runs.items()
            if run.terminal
            and run.completed_at is not None
            and run.completed_at < cutoff
        ]
        for run_id in expired:
            self._runs.pop(run_id, None)


# ── 进程内单例 ──────────────────────────────────────────────────
_manager: ChatRunManager | None = None


def get_chat_run_manager() -> ChatRunManager:
    """返回当前 Python 进程唯一的 ChatRunManager。"""
    global _manager
    if _manager is None:
        _manager = ChatRunManager()
    return _manager
