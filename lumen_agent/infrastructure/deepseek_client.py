"""基础设施：DeepSeek HTTP 客户端（`LLMClientPort` 的一个实现）。

职责边界：
- **只做 I/O 与 JSON 解析**：构造请求、处理响应、抛出可理解的 `RuntimeError`。
- **不做** HTTP 状态码到业务错误的最终映射（那属于 `api/routers` 层的职责，便于返回统一 API 契约）。

DeepSeek 使用 OpenAI 兼容接口：
- Endpoint：`{base_url}/v1/chat/completions`
- Header：`Authorization: Bearer <api_key>`

关于 `httpx.AsyncClient` 的生命周期：
- 当前实现为「每次 `chat()` / `chat_stream()` 临时创建 AsyncClient + 关闭」。
  - 优点：代码简单，不会在全局泄漏连接。
  - 缺点：极高 QPS 下连接复用差；后续可在 `lifespan` 创建全局 client，并通过 `api/dependency.py` 注入。

超时策略：
- `read=120s`：大模型生成可能较慢。
- `connect=10s`：连接建立失败应尽快失败，避免线程/协程长时间悬挂。
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx

from lumen_agent.config import Settings


class DeepSeekHttpClient:
    """调用 DeepSeek「OpenAI 兼容 Chat Completions」的最小客户端。"""

    def __init__(self, settings: Settings) -> None:
        """保存配置引用；不在构造函数里发起网络请求。"""
        self._settings = settings

    def _chat_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._settings.deepseek_api_key}",
            "Content-Type": "application/json",
        }

    def _build_chat_payload(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None,
        stream: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._settings.deepseek_model,
            "messages": messages,
        }
        if stream:
            payload["stream"] = True
        effective_temperature = (
            temperature if temperature is not None else self._settings.deepseek_temperature
        )
        if effective_temperature is not None:
            payload["temperature"] = effective_temperature
        if self._settings.deepseek_max_tokens is not None:
            payload["max_tokens"] = self._settings.deepseek_max_tokens
        if self._settings.deepseek_top_p is not None:
            payload["top_p"] = self._settings.deepseek_top_p
        return payload

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None = None,
    ) -> str:
        """POST `/v1/chat/completions` 并解析 assistant 文本。

        采样相关字段优先顺序：`chat(..., temperature=...)` 实参 > `Settings`（`.env`）>
        不传该键（由上游默认）。

        Raises:
            httpx.HTTPStatusError: 上游返回非 2xx（由 `raise_for_status()` 抛出）。
            httpx.RequestError: DNS/连接超时等传输层错误。
            RuntimeError: JSON 结构不符合最小可用形态（例如没有 choices / content 为空）。
        """
        url = f"{self._settings.deepseek_base_url}/v1/chat/completions"
        headers = self._chat_headers()
        payload = self._build_chat_payload(messages, temperature=temperature, stream=False)

        timeout = httpx.Timeout(120.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("upstream returned no choices")

        message = (choices[0] or {}).get("message") or {}
        content = message.get("content")

        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("upstream returned empty or non-text assistant content")

        return content

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None = None,
    ) -> AsyncIterator[str]:
        """POST `stream: true`，解析 SSE `data:` 行，逐段 yield 非空文本增量。"""
        url = f"{self._settings.deepseek_base_url}/v1/chat/completions"
        headers = self._chat_headers()
        payload = self._build_chat_payload(messages, temperature=temperature, stream=True)

        timeout = httpx.Timeout(120.0, connect=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line or line.startswith(":"):
                        continue
                    if not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        obj: dict[str, Any] = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    err = obj.get("error")
                    if err is not None:
                        if isinstance(err, dict):
                            msg = err.get("message") or json.dumps(err, ensure_ascii=False)
                        else:
                            msg = str(err)
                        raise RuntimeError(msg)

                    choices = obj.get("choices") or []
                    if not choices:
                        continue
                    delta = (choices[0] or {}).get("delta") or {}
                    piece = delta.get("content")
                    if isinstance(piece, str) and piece:
                        yield piece
