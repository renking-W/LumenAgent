"""VM 事件总线：内存异步 pub/sub，按 vm_id 分发实时事件。

用法
----
bus = get_vm_event_bus()

# 订阅（WebSocket 端调用）
sub_id, queue = await bus.subscribe("my-vm")
# 循环 queue.get() 消费事件

# 取消订阅（WS 断开时调用）
await bus.unsubscribe("my-vm", sub_id)

# 发布（execute_stream 内部调用）
await bus.publish("my-vm", {"type": "vm_event", ...})
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)

_MAX_QUEUE_SIZE = 256


class VmEventBus:
    """内存异步事件总线，按 vm_id 分发到所有订阅者。

    线程安全（asyncio.Lock），队列满时丢弃最早事件（防积压）。
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        # {vm_id: {subscriber_id: asyncio.Queue}}
        self._subscribers: dict[str, dict[str, asyncio.Queue]] = {}

    async def subscribe(self, vm_id: str) -> tuple[str, asyncio.Queue]:
        """订阅指定 VM 的事件。

        Returns:
            (subscriber_id, Queue) — 调用方应持续从 Queue 中 get 事件。
        """
        sub_id = uuid.uuid4().hex[:12]
        queue: asyncio.Queue = asyncio.Queue(maxsize=_MAX_QUEUE_SIZE)
        async with self._lock:
            subs = self._subscribers.get(vm_id)
            if subs is None:
                subs = {}
                self._subscribers[vm_id] = subs
            subs[sub_id] = queue
        logger.debug("VmEventBus 订阅: vm_id=%s sub_id=%s 当前订阅数=%d", vm_id, sub_id, len(subs))
        return sub_id, queue

    async def unsubscribe(self, vm_id: str, subscriber_id: str) -> None:
        """取消订阅，清理队列。"""
        async with self._lock:
            subs = self._subscribers.get(vm_id)
            if subs is None:
                return
            subs.pop(subscriber_id, None)
            if not subs:
                self._subscribers.pop(vm_id, None)
        logger.debug("VmEventBus 取消订阅: vm_id=%s sub_id=%s", vm_id, subscriber_id)

    async def publish(self, vm_id: str, event: dict[str, Any]) -> None:
        """向指定 VM 的所有订阅者广播事件。

        队列满时丢弃最早事件（put_nowait 失败 → get_nowait 丢弃再 put）。
        """
        async with self._lock:
            subs = self._subscribers.get(vm_id)
            if not subs:
                return
            # 快照当前订阅者列表（在锁内复制，避免迭代时被修改）
            queues = list(subs.values())

        for q in queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # 队列满 → 丢弃最早事件，再尝试放入
                try:
                    q.get_nowait()
                    q.put_nowait(event)
                except asyncio.QueueEmpty:
                    pass  # 极端竞态，丢弃即可

    async def subscriber_count(self, vm_id: str) -> int:
        """返回指定 VM 的当前订阅者数量（主要用于监控）。"""
        async with self._lock:
            subs = self._subscribers.get(vm_id)
            return len(subs) if subs else 0

    async def all_vm_ids(self) -> list[str]:
        """返回当前有订阅者的所有 vm_id 列表。"""
        async with self._lock:
            return list(self._subscribers.keys())


# ── 全局单例 ─────────────────────────────────────────────────────

_bus: VmEventBus | None = None


def get_vm_event_bus() -> VmEventBus:
    """返回应用全局唯一的 VmEventBus 实例。"""
    global _bus
    if _bus is None:
        _bus = VmEventBus()
    return _bus
