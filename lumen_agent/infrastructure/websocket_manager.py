"""WebSocket 连接管理器 —— 统一处理：握手机制、主动推送、被动接收、心跳、关闭。

职责边界：
- 只关心「怎么发、怎么收、怎么保活」
- 不关心「发什么内容」（业务层决定）

用法
----
mgr = get_ws_manager()

# 在 WebSocket 端点中
@router.websocket("/ws")
async def my_ws(ws: WebSocket):
    conn_id = await mgr.accept(ws)
    try:
        # 启动心跳
        hb = asyncio.create_task(mgr.start_heartbeat(conn_id, 30))
        msg = await mgr.receive_json(conn_id, timeout=60)
        await mgr.send_json(conn_id, {"reply": "ok"})
    finally:
        hb.cancel()
        await mgr.close(conn_id)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

_HEARTBEAT_INTERVAL = 30.0
_HEARTBEAT_TIMEOUT_FACTOR = 3  # 连续 3 次无 pong 则断开
_RECEIVE_TIMEOUT = 60.0


@dataclass
class _ConnectionState:
    """单个 WebSocket 连接的状态。"""

    websocket: WebSocket
    connected_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))
    last_pong: float = field(default_factory=time.monotonic)


class WebSocketConnectionManager:
    """WebSocket 连接管理器 —— 封装连接生命周期与基础通信。"""

    def __init__(self) -> None:
        self._connections: dict[str, _ConnectionState] = {}
        self._lock = asyncio.Lock()

    # ── 连接生命周期 ─────────────────────────────────────────────

    async def accept(self, websocket: WebSocket) -> str:
        """接受 WebSocket 握手并注册连接。

        Returns:
            唯一 connection_id（供后续 send / receive / close 使用）。
        """
        await websocket.accept()
        conn_id = uuid.uuid4().hex[:12]
        state = _ConnectionState(websocket=websocket)
        async with self._lock:
            self._connections[conn_id] = state
        logger.info("WebSocket 已连接: conn_id=%s", conn_id)
        return conn_id

    async def send_json(self, conn_id: str, data: dict[str, Any]) -> None:
        """向指定连接主动推送 JSON 消息。

        Raises:
            ConnectionError: 连接不存在或已断开。
            WebSocketDisconnect: 连接已断开（由调用方 catch）。
        """
        state = self._get_state(conn_id)
        try:
            await state.websocket.send_json(data)
        except WebSocketDisconnect:
            await self.close(conn_id)
            raise

    async def broadcast(self, data: dict[str, Any]) -> None:
        """广播 JSON 消息到所有活跃连接。"""
        async with self._lock:
            ids = list(self._connections.keys())
        for conn_id in ids:
            try:
                await self.send_json(conn_id, data)
            except (ConnectionError, WebSocketDisconnect):
                pass  # 单个连接失败不影响广播

    async def receive_json(
        self,
        conn_id: str,
        *,
        timeout: float = _RECEIVE_TIMEOUT,
    ) -> dict[str, Any] | None:
        """阻塞等待接收一条 JSON 消息。

        Args:
            conn_id: 连接 ID。
            timeout: 超时秒数（默认 60）。

        Returns:
            解析后的 dict，超时返回 None。

        Raises:
            WebSocketDisconnect: 连接已断开。
        """
        state = self._get_state(conn_id)
        try:
            raw = await asyncio.wait_for(state.websocket.receive_text(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("WebSocket 收到非法 JSON: conn_id=%s", conn_id)
            return None

    async def close(
        self,
        conn_id: str,
        *,
        code: int = 1000,
        reason: str = "",
    ) -> None:
        """使用指定关闭码关闭连接并清理资源。幂等。"""
        async with self._lock:
            state = self._connections.pop(conn_id, None)
        if state is None:
            return
        try:
            await state.websocket.close(code=code, reason=reason)
        except Exception:
            pass  # 关闭时忽略异常
        logger.info("WebSocket 已断开: conn_id=%s", conn_id)

    async def close_all(self) -> None:
        """关闭所有活跃连接（供 lifespan shutdown 调用）。"""
        async with self._lock:
            ids = list(self._connections.keys())
        for conn_id in ids:
            await self.close(conn_id)
        logger.info("所有 WebSocket 连接已关闭")

    # ── 心跳 ─────────────────────────────────────────────────────

    async def start_heartbeat(
        self,
        conn_id: str,
        interval: float = _HEARTBEAT_INTERVAL,
    ) -> None:
        """后台心跳协程：每 interval 秒发送 ping。

        若连续 3 次未收到 pong，则自动断开连接。
        调用方应在 finally 块中 cancel 此任务。
        """
        state = self._get_state(conn_id)
        try:
            while True:
                await asyncio.sleep(interval)
                # 检查超时
                if time.monotonic() - state.last_pong > interval * _HEARTBEAT_TIMEOUT_FACTOR:
                    logger.warning(
                        "WebSocket 心跳超时，自动断开: conn_id=%s", conn_id,
                    )
                    await self.close(conn_id)
                    return
                try:
                    await state.websocket.send_json({"type": "ping"})
                except WebSocketDisconnect:
                    logger.info("WebSocket 已断开（心跳发送失败）: conn_id=%s", conn_id)
                    await self.close(conn_id)
                    return
        except asyncio.CancelledError:
            pass  # 调用方主动取消

    # ── pong 更新 ────────────────────────────────────────────────

    async def update_pong(self, conn_id: str) -> None:
        """收到客户端 pong 后更新最后活跃时间。"""
        state = self._connections.get(conn_id)
        if state is not None:
            state.last_pong = time.monotonic()

    # ── 状态查询 ─────────────────────────────────────────────────

    @property
    def active_count(self) -> int:
        """当前活跃连接数。"""
        return len(self._connections)

    def is_active(self, conn_id: str) -> bool:
        """检查连接是否仍处于活跃状态。"""
        return conn_id in self._connections

    # ── 内部 ─────────────────────────────────────────────────────

    def _get_state(self, conn_id: str) -> _ConnectionState:
        """获取连接状态，不存在时抛 ConnectionError。"""
        state = self._connections.get(conn_id)
        if state is None:
            raise ConnectionError(f"WebSocket 连接不存在: {conn_id}")
        return state


# ── 全局单例 ─────────────────────────────────────────────────────

_manager: WebSocketConnectionManager | None = None


def get_ws_manager() -> WebSocketConnectionManager:
    """返回应用全局唯一的 WebSocketConnectionManager 实例。"""
    global _manager
    if _manager is None:
        _manager = WebSocketConnectionManager()
    return _manager
