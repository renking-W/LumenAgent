"""会话-SSE 连接注册表：维护 session_id → StreamHandle 映射，供中断时关闭上游连接。"""

from __future__ import annotations

import asyncio
import logging

from lumen_agent.infrastructure.http_pool import StreamHandle

logger = logging.getLogger(__name__)


class SessionSSERegistry:
    """全局会话-SSE 连接注册表。

    每个 ``session_id`` 同时只允许一个活跃的流式连接。
    中断时通过 ``interrupt()`` 关闭对应的 ``StreamHandle``。
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._active: dict[str, StreamHandle] = {}

    async def register(self, session_id: str, handle: StreamHandle) -> None:
        """注册会话的流式连接句柄。

        若已有活跃连接，先中断旧的（幂等抢占）。
        """
        async with self._lock:
            old = self._active.get(session_id)
            if old is not None:
                logger.warning("session=%s 已有活跃连接，抢占中断旧连接", session_id)
                await old.close()
            self._active[session_id] = handle

    async def unregister(self, session_id: str) -> None:
        """取消注册（正常结束/错误后调用）。"""
        async with self._lock:
            self._active.pop(session_id, None)

    async def interrupt(self, session_id: str) -> bool:
        """中断指定会话的流式连接。

        Returns:
            True  — 找到并关闭了连接
            False — 该会话没有活跃连接
        """
        async with self._lock:
            handle = self._active.pop(session_id, None)
        if handle is None:
            return False
        logger.info("session=%s 收到中断请求，关闭 StreamHandle", session_id)
        await handle.close()
        return True


# ── 全局单例 ─────────────────────────────────────────────────────

_registry: SessionSSERegistry | None = None


def get_sse_registry() -> SessionSSERegistry:
    """返回应用全局唯一的 ``SessionSSERegistry`` 实例。"""
    global _registry
    if _registry is None:
        _registry = SessionSSERegistry()
    return _registry
