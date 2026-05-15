"""LLM 调用链异常 → 与 `HTTPException.detail` / SSE `error.message` 一致的文案。"""

from __future__ import annotations

import httpx

_UPSTREAM_RESPONSE_TEXT_MAX = 2000


def llm_chain_failure_detail(exc: BaseException) -> str:
    """将 LLM 链路异常转为对外说明字符串（与 HTTP detail / SSE error 一致）。"""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.text[:_UPSTREAM_RESPONSE_TEXT_MAX]
    if isinstance(exc, httpx.RequestError):
        return str(exc)
    if isinstance(exc, RuntimeError):
        return str(exc)
    return str(exc)


def llm_chain_failure_http_status(_exc: BaseException) -> int:
    """LLM 链路失败时映射的 HTTP 状态码（当前固定 502）。"""
    return 502
