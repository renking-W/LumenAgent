"""DeepSeek OpenAI 兼容 `POST /v1/chat/completions`；HTTP 错误映射在路由层。"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx

from lumen_agent.config import Settings


class DeepSeekHttpClient:
    """DeepSeek OpenAI 兼容 Chat Completions 客户端。"""

    def __init__(self, settings: Settings) -> None:
        """保存 ``Settings``，请求时再读其中的 base_url、key、模型等。"""
        self._settings = settings

    def _chat_headers(self) -> dict[str, str]:
        """构造 Chat Completions 请求头（Bearer + JSON）。"""
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
        """组装请求 JSON：模型、messages、可选 stream / 采样参数。"""
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
        """同步调用上游，解析 ``choices[0].message.content`` 为完整字符串。"""
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
        """流式调用上游，解析 SSE ``data:`` 行，逐段 yield ``delta.content``。"""
        url = f"{self._settings.deepseek_base_url}/v1/chat/completions"
        headers = self._chat_headers()
        payload = self._build_chat_payload(messages, temperature=temperature, stream=True)

        timeout = httpx.Timeout(120.0, connect=10.0)
        # 异步发http请求
        async with httpx.AsyncClient(timeout=timeout) as client:
            # 异步调用会话流
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                # 获取大模型返回数据（异步获取）
                async for line in response.aiter_lines():
                    # 去除首尾空白
                    line = line.strip()
                    # 去除注释行（以 : 开头的是 SSE 注释（heartbeat 或调试信息），不需要处理）
                    if not line or line.startswith(":"):
                        continue
                    # 去除非数据行
                    if not line.startswith("data:"):
                        continue
                    # 获取返回具体数据
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        obj: dict[str, Any] = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    # 有error数据直接中断
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
