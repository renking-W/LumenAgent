"""Sub-Agent WebSocket 端点：WS /v1/sub-agents/ws — 前端实时订阅 sub-agent 事件。

订阅流程：
1. 前端连接 WS → 后端 accept
2. 前端发 {"type":"subscribe","run_id":"xxx"} → 后端订阅 SubAgentEventBus
3. 后端持续转发事件到 WebSocket
4. 前端发 {"type":"unsubscribe"} / 断连 → 清理订阅
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from lumen_agent.infrastructure.sub_agent_event_bus import get_sub_agent_event_bus
from lumen_agent.infrastructure.websocket_manager import get_ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/sub-agents", tags=["sub-agents"])


@router.websocket("/ws")
async def sub_agent_websocket(websocket: WebSocket):
    """WebSocket 端点：前端连接后订阅指定 run 的实时事件。"""
    mgr = get_ws_manager()
    conn_id = await mgr.accept(websocket)

    heartbeat_task: asyncio.Task | None = None
    relay_task: asyncio.Task | None = None
    subscriber_id: str | None = None
    current_run_id: str | None = None

    try:
        heartbeat_task = asyncio.create_task(
            mgr.start_heartbeat(conn_id, interval=30),
        )

        while True:
            msg = await mgr.receive_json(conn_id, timeout=60)
            if msg is None:
                continue

            msg_type = msg.get("type")

            if msg_type == "subscribe":
                current_run_id = msg.get("run_id", "")
                if not current_run_id:
                    await mgr.send_json(conn_id, {
                        "type": "error",
                        "message": "run_id is required",
                    })
                    continue

                bus = get_sub_agent_event_bus()
                subscriber_id, queue = await bus.subscribe(current_run_id)

                async def _relay():
                    try:
                        while True:
                            event = await queue.get()
                            await mgr.send_json(conn_id, event)
                    except asyncio.CancelledError:
                        pass
                    except Exception:
                        logger.exception("Sub-Agent 事件转发异常")

                relay_task = asyncio.create_task(_relay())
                await mgr.send_json(conn_id, {
                    "type": "subscribed",
                    "run_id": current_run_id,
                })
                logger.info("SubAgent WS 订阅: conn_id=%s run_id=%s", conn_id, current_run_id)

            elif msg_type == "unsubscribe":
                break

            elif msg_type == "pong":
                await mgr.update_pong(conn_id)

    except WebSocketDisconnect:
        logger.info("SubAgent WS 客户端断开: conn_id=%s", conn_id)
    except Exception:
        logger.exception("SubAgent WS 异常: conn_id=%s", conn_id)
    finally:
        if relay_task is not None:
            relay_task.cancel()
        if heartbeat_task is not None:
            heartbeat_task.cancel()
        if current_run_id is not None and subscriber_id is not None:
            await get_sub_agent_event_bus().unsubscribe(current_run_id, subscriber_id)
        await mgr.close(conn_id)
