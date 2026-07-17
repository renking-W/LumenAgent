"""应用全局 HTTP 连接池：统一管理 httpx 共享连接与流式连接的独立生命周期。"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Callable
from typing import Any, Literal

import httpx

from lumen_agent.config import Settings

logger = logging.getLogger(__name__)

# ── 默认超时 ─────────────────────────────────────────────────────
_DEFAULT_TIMEOUT = httpx.Timeout(120.0, connect=10.0)


# ══════════════════════════════════════════════════════════════════
# StreamHandle
# ══════════════════════════════════════════════════════════════════

class StreamHandle:
    """一次流式 HTTP 连接的生命周期句柄。拥有独立的 ``httpx.AsyncClient``，
    可独立关闭，不依赖外部进程状态。
    """

    def __init__(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        timeout: httpx.Timeout | None = None,
        on_close: Callable[[], None] | None = None,
        protocol: Literal["chat_completions", "responses"] = "chat_completions",
    ) -> None:
        self._method = method
        self._url = url
        self._headers = dict(headers or {})
        self._json = json
        self._timeout = timeout or _DEFAULT_TIMEOUT
        self._on_close = on_close
        self._protocol = protocol

        self._client: httpx.AsyncClient | None = None
        self._response: httpx.Response | None = None
        self._state: str = "CREATED"

    # ── public API ───────────────────────────────────────────────

    async def connect(self) -> None:
        """发起请求，获取流式响应。必须最先调用，仅调用一次。"""
        if self._state != "CREATED":
            raise RuntimeError(f"StreamHandle.connect() 不可重复调用（state={self._state}）")

        self._state = "CONNECTING"
        self._client = httpx.AsyncClient(timeout=self._timeout)
        request = self._client.build_request(
            self._method, self._url,
            headers=self._headers,
            json=self._json,
        )
        try:
            self._response = await self._client.send(request, stream=True)
        except Exception:
            self._state = "ERROR"
            await self._close_resources()
            raise

        if self._response.status_code >= 400:
            status_code = self._response.status_code
            body = await self._response.aread()
            try:
                detail = body.decode("utf-8", errors="replace")[:4000]
            except Exception:
                detail = repr(body)
            self._state = "ERROR"
            await self._close_resources()
            raise RuntimeError(
                f"upstream HTTP {status_code}: {detail}"
            )

        self._state = "STREAMING"

    async def receive(self) -> AsyncIterator[tuple[str, str | dict]]:
        """逐行读取 SSE ``data:`` 事件，yield ``(kind, data)``。

        kind 取值:
          "content"           – 文本增量（str）
          "reasoning_content" – 思维链增量（str）
          "tool_use"          – 工具调用块（dict）
        """
        if self._state != "STREAMING":
            raise RuntimeError(f"StreamHandle.receive() 需在 STREAMING 状态调用（state={self._state}）")
        if self._response is None:
            return

        if self._protocol == "responses":
            async for item in self._receive_responses():
                yield item
            return

        pending_tool_calls: dict[int, dict[str, str]] = {}
        done = False

        async for line in self._response.aiter_lines():
            if done:
                # 收到 [DONE] 后继续读完剩余数据以排空流，
                # 避免 break 导致 GeneratorExit 传播 → anyio 冲突
                continue

            line = line.strip()
            if not line or line.startswith(":"):
                continue
            if not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if data_str == "[DONE]":
                done = True
                continue
            try:
                obj: dict[str, Any] = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            err = obj.get("error")
            if err is not None:
                msg = (
                    err.get("message") or json.dumps(err, ensure_ascii=False)
                    if isinstance(err, dict)
                    else str(err)
                )
                raise RuntimeError(msg)

            choices = obj.get("choices") or []
            if not choices:
                continue
            choice = choices[0] or {}
            delta: dict[str, Any] = choice.get("delta") or {}

            for field in ("reasoning", "reasoning_content", "content"):
                piece = delta.get(field)
                if isinstance(piece, str) and piece:
                    yield (field, piece)

            tc_deltas: list[dict] = delta.get("tool_calls") or []
            for tc_delta in tc_deltas:
                idx: int = tc_delta.get("index", 0)
                if idx not in pending_tool_calls:
                    pending_tool_calls[idx] = {
                        "id": tc_delta.get("id", ""),
                        "name": (tc_delta.get("function") or {}).get("name", ""),
                        "arguments": "",
                    }
                args_piece = (tc_delta.get("function") or {}).get("arguments", "")
                if args_piece:
                    pending_tool_calls[idx]["arguments"] += args_piece

        # 流结束后 yield 累积的工具调用
        if pending_tool_calls:
            for tc in pending_tool_calls.values():
                try:
                    parsed_input = json.loads(tc["arguments"]) if tc["arguments"] else {}
                except json.JSONDecodeError:
                    parsed_input = {"_raw": tc["arguments"]}
                yield (
                    "tool_use",
                    {
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["name"],
                        "input": parsed_input,
                    },
                )


    async def _receive_responses(self) -> AsyncIterator[tuple[str, str | dict]]:
        """Parse semantic SSE events emitted by the OpenAI Responses API."""
        if self._response is None:
            return

        async for line in self._response.aiter_lines():
            line = line.strip()
            if not line or line.startswith(":") or not line.startswith("data:"):
                continue
            data_str = line[5:].strip()
            if data_str == "[DONE]":
                continue
            try:
                event: dict[str, Any] = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            event_type = event.get("type", "")
            if event_type == "error":
                error = event.get("error") or event
                message = error.get("message") if isinstance(error, dict) else str(error)
                raise RuntimeError(message or "OpenAI Responses API stream failed")
            if event_type == "response.failed":
                response = event.get("response") or {}
                error = response.get("error") or {}
                message = error.get("message") if isinstance(error, dict) else str(error)
                raise RuntimeError(message or "OpenAI Responses API response failed")

            delta = event.get("delta")
            if event_type in {"response.output_text.delta", "response.refusal.delta"}:
                if isinstance(delta, str) and delta:
                    yield ("content", delta)
                continue
            if event_type in {
                "response.reasoning_summary_text.delta",
                "response.reasoning_text.delta",
            }:
                if isinstance(delta, str) and delta:
                    yield ("reasoning_content", delta)
                continue

            if event_type != "response.output_item.done":
                continue
            output_item = event.get("item") or {}
            if output_item.get("type") != "function_call":
                continue
            raw_arguments = output_item.get("arguments", "")
            try:
                parsed_input = json.loads(raw_arguments) if raw_arguments else {}
            except json.JSONDecodeError:
                parsed_input = {"_raw": raw_arguments}
            yield (
                "tool_use",
                {
                    "type": "tool_use",
                    "id": output_item.get("call_id") or output_item.get("id", ""),
                    "name": output_item.get("name", ""),
                    "input": parsed_input,
                },
            )

    async def close(self) -> None:
        """关闭连接并销毁独立 client。可反复调用，幂等。"""
        if self._state == "CLOSED":
            return
        self._state = "CLOSED"
        await self._close_resources()
        if self._on_close:
            self._on_close()

    # ── 内部 ─────────────────────────────────────────────────────

    async def _close_resources(self) -> None:
        """关闭 response 和 client，幂等。"""
        resp = self._response
        self._response = None
        if resp is not None:
            try:
                await resp.aclose()
            except Exception:
                logger.debug("StreamHandle 关闭 response 时忽略异常", exc_info=True)

        client = self._client
        self._client = None
        if client is not None:
            try:
                await client.aclose()
            except Exception:
                logger.debug("StreamHandle 关闭 client 时忽略异常", exc_info=True)


# ══════════════════════════════════════════════════════════════════
# HttpPool
# ══════════════════════════════════════════════════════════════════

class HttpPool:
    """应用全局 HTTP 连接池。

    - ``shared_client`` 用于非流式请求（chat / embedding / web_fetch）。
    - 流式请求通过 ``send_stream()`` 返回独立的 ``StreamHandle``。
    - ``close_all()`` 统一关闭共享 client 与所有活跃的流式连接。
    """

    def __init__(self) -> None:
        self._shared_client: httpx.AsyncClient | None = None
        self._active_handles: list[StreamHandle] = []
        self._initialized = False

    # ── 初始化 ───────────────────────────────────────────────────

    def init(self, settings: Settings | None = None) -> None:
        """延迟初始化共享 client。幂等。"""
        if self._initialized:
            return
        self._initialized = True
        self._shared_client = httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT)

    # ── 非流式 ───────────────────────────────────────────────────

    async def send(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        timeout: httpx.Timeout | float | None = None,
    ) -> httpx.Response:
        """通用非流式请求。复用共享 client。"""
        self._ensure_initialized()
        if self._shared_client is None:
            raise RuntimeError("HttpPool 未初始化")

        effective_timeout = (
            httpx.Timeout(timeout) if isinstance(timeout, (int, float)) and timeout > 0
            else timeout or _DEFAULT_TIMEOUT
        )

        response = await self._shared_client.request(
            method, url,
            headers=headers or {},
            json=json,
            timeout=effective_timeout,
        )
        return response

    # ── 流式 ─────────────────────────────────────────────────────

    def send_stream(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        protocol: Literal["chat_completions", "responses"] = "chat_completions",
    ) -> StreamHandle:
        """流式请求。返回独立的 ``StreamHandle``，关闭时自动从活跃列表移除。"""
        self._ensure_initialized()
        handle = StreamHandle(
            method, url,
            headers=headers,
            json=json,
            timeout=_DEFAULT_TIMEOUT,
            on_close=lambda: self._remove_handle(handle),
            protocol=protocol,
        )
        self._active_handles.append(handle)
        return handle

    def _remove_handle(self, handle: StreamHandle) -> None:
        """从活跃列表中移除已关闭的 handle。"""
        try:
            self._active_handles.remove(handle)
        except ValueError:
            pass

    # ── 生命周期 ────────────────────────────────────────────────

    async def close_all(self) -> None:
        """关闭共享 client 和所有活跃的流式连接。幂等。"""
        self._initialized = False

        # 关闭所有活跃的 StreamHandle
        handles = self._active_handles[:]
        self._active_handles.clear()
        for h in handles:
            try:
                await h.close()
            except Exception:
                logger.debug("HttpPool.close_all 关闭 StreamHandle 时忽略异常", exc_info=True)

        # 关闭共享 client
        client = self._shared_client
        self._shared_client = None
        if client is not None:
            try:
                await client.aclose()
            except Exception:
                logger.debug("HttpPool.close_all 关闭 shared_client 时忽略异常", exc_info=True)

    # ── 内部 ─────────────────────────────────────────────────────

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            self.init()


# ── 单例工厂 ─────────────────────────────────────────────────────

_pool: HttpPool | None = None


def get_http_pool() -> HttpPool:
    """返回应用全局唯一的 ``HttpPool`` 实例。"""
    global _pool
    if _pool is None:
        _pool = HttpPool()
    return _pool
