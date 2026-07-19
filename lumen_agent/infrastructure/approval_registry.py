"""工具调用审批注册表：session_id → 待审批的工具调用，支持挂起等待和超时自动拒绝。

设计同 SSERegistry（全局单例），审批请求通过 POST /v1/chat/stream/approve 写入，
Agent 循环通过 wait_for_all() 挂起等待全部决策。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PendingApproval:
    """单个会话的待审批状态。"""

    session_id: str
    tool_calls: list[dict[str, Any]]
    decisions: dict[str, bool] = field(default_factory=dict)
    event: asyncio.Event = field(default_factory=asyncio.Event)

    @property
    def all_decided(self) -> bool:
        return len(self.decisions) == len(self.tool_calls)

    @property
    def undecided_ids(self) -> list[str]:
        decided = set(self.decisions.keys())
        return [tc["id"] for tc in self.tool_calls if tc["id"] not in decided]


class ApprovalRegistry:
    """全局审批注册表。"""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._pending: dict[str, PendingApproval] = {}

    async def register(
        self,
        session_id: str,
        tool_calls: list[dict[str, Any]],
    ) -> None:
        """注册一组待审批的工具调用。若该 session 已有待审批项，覆盖旧项。"""
        async with self._lock:
            self._pending[session_id] = PendingApproval(
                session_id=session_id,
                tool_calls=list(tool_calls),
            )
        logger.info(
            "审批注册: session=%s tools=%s",
            session_id, [t["name"] for t in tool_calls],
        )

    async def approve(
        self,
        session_id: str,
        tool_call_id: str,
        decision: bool,
    ) -> bool:
        """提交单个工具调用的审批决策。全部决策完成后释放 wait_for_all。

        Returns:
            True  — 决策已生效
            False — 没有待审批项、工具不存在或该工具已经审批
        """
        async with self._lock:
            pa = self._pending.get(session_id)
            if pa is None:
                return False
            valid_ids = {tc["id"] for tc in pa.tool_calls}
            if tool_call_id not in valid_ids or tool_call_id in pa.decisions:
                return False
            pa.decisions[tool_call_id] = decision
            if pa.all_decided:
                pa.event.set()
        logger.info(
            "审批决策: session=%s tool_call=%s decision=%s",
            session_id, tool_call_id, decision,
        )
        return True

    async def wait_for_all(
        self,
        session_id: str,
        timeout: float = 300,
    ) -> dict[str, bool]:
        """等待全部待审批工具调用都有决策。

        超时后未决的工具调用自动设为拒绝。
        返回 {tool_call_id: bool} 字典。
        """
        async with self._lock:
            pa = self._pending.get(session_id)
        if pa is None:
            return {}

        try:
            await asyncio.wait_for(pa.event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning("审批超时: session=%s 未决工具自动拒绝", session_id)
            async with self._lock:
                for tc_id in pa.undecided_ids:
                    pa.decisions[tc_id] = False
                pa.event.set()

        async with self._lock:
            result = pa.decisions.copy()
            self._pending.pop(session_id, None)
        return result

    async def unregister(self, session_id: str) -> None:
        """中断时清理待审批项（不触发 event）。"""
        async with self._lock:
            pa = self._pending.pop(session_id, None)
        if pa is not None:
            logger.info("审批清理: session=%s", session_id)

    async def has_pending(self, session_id: str) -> bool:
        """检查 session 是否有待审批项。"""
        async with self._lock:
            return session_id in self._pending


# ── 全局单例 ─────────────────────────────────────────────────────

_registry: ApprovalRegistry | None = None


def get_approval_registry() -> ApprovalRegistry:
    """返回应用全局唯一的 ApprovalRegistry 实例。"""
    global _registry
    if _registry is None:
        _registry = ApprovalRegistry()
    return _registry
