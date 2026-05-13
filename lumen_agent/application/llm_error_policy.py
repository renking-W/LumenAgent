"""LLM 调用链异常 → 对外说明文案 / HTTP 状态码（一次性接口与 SSE 共用）。

不依赖 FastAPI，便于单测与在 `StreamingResponse` 的 async generator 内复用同一套 `detail`。
"""

from __future__ import annotations

import httpx

# 与历史 `post_chat` 行为对齐：避免把巨大 HTML/JSON 原样塞给客户端。
_UPSTREAM_RESPONSE_TEXT_MAX = 2000


def llm_chain_failure_detail(exc: BaseException) -> str:
    """生成与 `HTTPException.detail` 或 SSE `error.data.message` 一致的说明文本。"""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.text[:_UPSTREAM_RESPONSE_TEXT_MAX]
    if isinstance(exc, httpx.RequestError):
        return str(exc)
    if isinstance(exc, RuntimeError):
        return str(exc)
    return str(exc)


def llm_chain_failure_http_status(_exc: BaseException) -> int:
    """当前策略：上游/网络/解析类问题统一映射为 502（网关/上游不可用语义）。"""
    return 502
