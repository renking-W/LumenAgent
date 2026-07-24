"""VM WebSocket 端点：WS /v1/vm/ws — 前端订阅 VM 实时事件。

订阅流程：
1. 前端连接 WS → 后端 accept
2. 认证开启时，前端先发送 auth 消息
3. 前端发 {"type":"subscribe","vm_id":"xxx"} → 后端订阅 VmEventBus
4. 后端持续转发 VM 事件到 WebSocket
5. Token 刷新后发送 auth_refresh，断连时清理订阅
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from lumen_agent.api.websocket_auth import (
    WebSocketAuthenticationError,
    authenticate_initial_message,
    authenticated_receive_timeout,
    ensure_websocket_admin_active,
    refresh_websocket_auth,
)
from lumen_agent.config import get_settings

from lumen_agent.infrastructure.vm_event_bus import get_vm_event_bus
from lumen_agent.infrastructure.websocket_manager import get_ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/vm", tags=["vm"])


@router.websocket("/ws")
async def vm_websocket(websocket: WebSocket):
    """WebSocket 端点：前端连接后订阅 VM 事件。"""
    mgr = get_ws_manager()
    conn_id = await mgr.accept(websocket)
    settings = get_settings()
    auth_context = None

    heartbeat_task: asyncio.Task | None = None
    relay_task: asyncio.Task | None = None
    subscriber_id: str | None = None
    current_vm_id: str | None = None

    try:
        # 认证成功后再启动心跳
        auth_context = await authenticate_initial_message(
            mgr, conn_id, settings,
        )

        heartbeat_task = asyncio.create_task(
            mgr.start_heartbeat(conn_id, interval=30),
        )

        # 每轮接收前复查管理员状态，并把等待时长限制在 Token 剩余寿命内。
        while True:
            if auth_context is not None:
                auth_context = await ensure_websocket_admin_active(
                    auth_context, settings,
                )
            timeout = authenticated_receive_timeout(auth_context)
            msg = await mgr.receive_json(conn_id, timeout=timeout)
            if msg is None:
                continue  # 超时无消息，重试（heartbeat 任务负责保活）

            msg_type = msg.get("type")

            # 认证控制消息只更新连接身份，不进入 VM 订阅业务。
            if msg_type == "auth_refresh":
                if auth_context is None:
                    await mgr.send_json(conn_id, {
                        "type": "error",
                        "message": "当前连接未启用认证",
                    })
                    continue
                auth_context = await refresh_websocket_auth(
                    mgr,
                    conn_id,
                    msg,
                    settings,
                )
                continue

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

    # 认证错误先通知前端，再使用约定的 4401/4403/4408 关闭连接。
    except WebSocketAuthenticationError as exc:
        logger.warning("VM WebSocket 认证失败: conn_id=%s detail=%s", conn_id, exc.detail)
        try:
            await mgr.send_json(conn_id, {
                "type": "auth_error",
                "message": exc.detail,
            })
        except (ConnectionError, WebSocketDisconnect):
            pass
        await mgr.close(
            conn_id,
            code=exc.code,
            reason="authentication failed",
        )
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
