"""Sub-Agent 事件总线：内存异步 pub/sub，按 run_id 分发实时事件。

结构与 vm_event_bus.py 完全对称，只把 vm_id 换成 run_id。

用法
----
bus = get_sub_agent_event_bus()

# 订阅（WebSocket 端调用）
sub_id, queue = await bus.subscribe("run-abc")

# 发布（SubAgentService 内部调用）
await bus.publish("run-abc", {"type": "sub_agent_event", ...})

# 取消订阅
await bus.unsubscribe("run-abc", sub_id)
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)

_MAX_QUEUE_SIZE = 512


class SubAgentEventBus:
    """内存异步事件总线，按 run_id 分发到所有订阅者。"""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._subscribers: dict[str, dict[str, asyncio.Queue]] = {}

    async def subscribe(self, run_id: str) -> tuple[str, asyncio.Queue]:
        sub_id = uuid.uuid4().hex[:12]
        queue: asyncio.Queue = asyncio.Queue(maxsize=_MAX_QUEUE_SIZE)
        async with self._lock:
            subs = self._subscribers.setdefault(run_id, {})
            subs[sub_id] = queue
        logger.debug("SubAgentEventBus 订阅: run_id=%s sub_id=%s", run_id, sub_id)
        return sub_id, queue

    async def unsubscribe(self, run_id: str, subscriber_id: str) -> None:
        async with self._lock:
            subs = self._subscribers.get(run_id)
            if not subs:
                return
            subs.pop(subscriber_id, None)
            if not subs:
                self._subscribers.pop(run_id, None)
        logger.debug("SubAgentEventBus 取消订阅: run_id=%s sub_id=%s", run_id, subscriber_id)

    async def publish(self, run_id: str, event: dict[str, Any]) -> None:
        async with self._lock:
            subs = self._subscribers.get(run_id)
            if not subs:
                return
            queues = list(subs.values())

        for q in queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except asyncio.QueueEmpty:
                    pass

    async def subscriber_count(self, run_id: str) -> int:
        async with self._lock:
            subs = self._subscribers.get(run_id)
            return len(subs) if subs else 0

    async def all_run_ids(self) -> list[str]:
        async with self._lock:
            return list(self._subscribers.keys())


# ── 全局单例 ─────────────────────────────────────────────────────

_bus: SubAgentEventBus | None = None


def get_sub_agent_event_bus() -> SubAgentEventBus:
    """返回应用全局唯一的 SubAgentEventBus 实例。"""
    global _bus
    if _bus is None:
        _bus = SubAgentEventBus()
    return _bus
