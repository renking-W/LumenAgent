"""VM WebSocket 端点：WS /v1/vm/ws — 前端订阅 VM 实时事件。

订阅流程：
1. 前端连接 WS → 后端 accept
2. 前端发 {"type":"subscribe","vm_id":"xxx"} → 后端订阅 VmEventBus
3. 后端持续转发 VM 事件到 WebSocket
4. 前端发 {"type":"unsubscribe"} / 断连 → 后端清理订阅
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from lumen_agent.infrastructure.vm_event_bus import get_vm_event_bus
from lumen_agent.infrastructure.websocket_manager import get_ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/vm", tags=["vm"])


@router.websocket("/ws")
async def vm_websocket(websocket: WebSocket):
    """WebSocket 端点：前端连接后订阅 VM 事件。"""
    mgr = get_ws_manager()
    conn_id = await mgr.accept(websocket)

    heartbeat_task: asyncio.Task | None = None
    relay_task: asyncio.Task | None = None
    subscriber_id: str | None = None
    current_vm_id: str | None = None

    try:
        # 启动心跳
        heartbeat_task = asyncio.create_task(
            mgr.start_heartbeat(conn_id, interval=30),
        )

        while True:
            msg = await mgr.receive_json(conn_id, timeout=60)
            if msg is None:
                continue  # 超时无消息，重试（heartbeat 任务负责保活）

            msg_type = msg.get("type")

            if msg_type == "subscribe":
                current_vm_id = msg.get("vm_id", "")
                if not current_vm_id:
                    await mgr.send_json(conn_id, {
                        "type": "error",
                        "message": "vm_id is required",
                    })
                    continue

                bus = get_vm_event_bus()
                subscriber_id, queue = await bus.subscribe(current_vm_id)

                # 启动转发协程：队列 → WebSocket
                async def _relay():
                    try:
                        while True:
                            event = await queue.get()
                            # 添加 source 标记（execute_stream 里标记为 system，这里可覆盖）
                            event["source"] = event.get("source", "system")
                            await mgr.send_json(conn_id, event)
                    except asyncio.CancelledError:
                        pass
                    except Exception:
                        logger.exception("VM 事件转发异常")

                relay_task = asyncio.create_task(_relay())
                await mgr.send_json(conn_id, {
                    "type": "subscribed",
                    "vm_id": current_vm_id,
                })
                logger.info(
                    "VM WebSocket 订阅成功: conn_id=%s vm_id=%s",
                    conn_id, current_vm_id,
                )

            elif msg_type == "unsubscribe":
                logger.info(
                    "VM WebSocket 取消订阅: conn_id=%s vm_id=%s",
                    conn_id, current_vm_id,
                )
                break

            elif msg_type == "pong":
                await mgr.update_pong(conn_id)

    except WebSocketDisconnect:
        logger.info("VM WebSocket 客户端断开: conn_id=%s", conn_id)
    except Exception:
        logger.exception("VM WebSocket 异常: conn_id=%s", conn_id)
    finally:
        # 清理
        if relay_task is not None:
            relay_task.cancel()
        if heartbeat_task is not None:
            heartbeat_task.cancel()
        if current_vm_id is not None and subscriber_id is not None:
            await get_vm_event_bus().unsubscribe(current_vm_id, subscriber_id)
        await mgr.close(conn_id)
