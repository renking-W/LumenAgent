"""Agent 运行时上下文管理：轮次裁剪、tool_result 截断、防无限循环保护。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field


# ──────────────────────────────────────────────
# ContextManager
# ──────────────────────────────────────────────

class ContextManager:
    """基于内部消息格式的上下文管理。

    max_turns 取 Settings.summary_threshold_turns，与摘要窗口保持一致。
    """

    def __init__(self, max_turns: int = 6, max_tool_result_chars: int = 20000) -> None:
        self.max_turns = max_turns
        self.max_tool_result_chars = max_tool_result_chars

    # ── 轮次识别 ──────────────────────────────

    def identify_complete_turns(
        self, messages: list[dict]
    ) -> list[list[dict]]:
        """将消息列表按"非 tool_result 的 user 消息"切分为完整轮次。

        同一轮次包含：user 问题 + assistant 回复 + 可能的多轮 tool_use/tool_result。
        """
        turns: list[list[dict]] = []
        current: list[dict] = []

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", [])

            is_tool_result_user = role == "user" and _has_only_tool_results(content)

            if role == "user" and not is_tool_result_user:
                # 新轮次开始：将上一轮存入 turns
                if current:
                    turns.append(current)
                current = [msg]
            else:
                current.append(msg)

        if current:
            turns.append(current)

        return turns

    def trim_to_max_turns(self, messages: list[dict]) -> list[dict]:
        """保留最近 max_turns 轮，丢弃更早的轮次。"""
        turns = self.identify_complete_turns(messages)
        if len(turns) <= self.max_turns:
            return messages
        keep = turns[-self.max_turns :]
        return [msg for turn in keep for msg in turn]

    # ── tool_result 截断 ──────────────────────

    def truncate_tool_results(self, messages: list[dict]) -> list[dict]:
        """截断超过上限的 tool_result 块内容，防止上下文溢出。"""
        for msg in messages:
            for block in msg.get("content", []):
                if (
                    isinstance(block, dict)
                    and block.get("type") == "tool_result"
                    and isinstance(block.get("content"), str)
                    and len(block["content"]) > self.max_tool_result_chars
                ):
                    original_len = len(block["content"])
                    block["content"] = (
                        block["content"][: self.max_tool_result_chars]
                        + f"\n...[truncated, original {original_len} chars]"
                    )
        return messages


def _has_only_tool_results(content: list | str) -> bool:
    """判断 user 消息是否仅包含 tool_result 块（区别于真实用户输入）。"""
    if not isinstance(content, list):
        return False
    return bool(content) and all(
        isinstance(b, dict) and b.get("type") == "tool_result" for b in content
    )


# ──────────────────────────────────────────────
# ToolExecutionGuard
# ──────────────────────────────────────────────

@dataclass
class ToolGuardResult:
    """防循环检查结果。"""

    allowed: bool
    reason: str = ""
    is_critical: bool = False   # True → 硬中断循环


class ToolExecutionGuard:
    """防无限循环保护。

    维护调用历史（最近 50 条），按三道防线拦截异常重复调用：
      1. 同工具 + 同参数调用 ≥ MAX_SAME_ARGS 次 → 软拦截
      2. 同工具连续失败 ≥ MAX_TOOL_FAILURES 次   → 软拦截
      3. 总连续失败 ≥ MAX_TOTAL_FAILURES 次       → 硬中断
    """

    MAX_SAME_ARGS: int = 5
    MAX_TOOL_FAILURES: int = 6
    MAX_TOTAL_FAILURES: int = 8
    _HISTORY_LIMIT: int = 50

    def __init__(self) -> None:
        # (name, args_hash, success)
        self._history: list[tuple[str, str, bool]] = []

    def check(self, tool_name: str, args: dict) -> ToolGuardResult:
        """执行前检查，返回是否允许执行。"""
        args_hash = _hash_args(args)

        # 1. 同工具 + 同参数重复调用
        same_args_count = sum(
            1
            for n, h, _ in self._history
            if n == tool_name and h == args_hash
        )
        if same_args_count >= self.MAX_SAME_ARGS:
            return ToolGuardResult(
                allowed=False,
                reason=(
                    f"工具 '{tool_name}' 使用相同参数已连续调用 {same_args_count} 次，已阻止重复执行。"
                ),
            )

        # 2. 同工具连续失败
        same_tool_fails = sum(
            1 for n, _, s in self._history if n == tool_name and not s
        )
        if same_tool_fails >= self.MAX_TOOL_FAILURES:
            return ToolGuardResult(
                allowed=False,
                reason=(
                    f"工具 '{tool_name}' 已连续失败 {same_tool_fails} 次，已阻止继续调用。"
                ),
            )

        # 3. 全局连续失败（硬中断）
        total_fails = sum(1 for _, _, s in self._history if not s)
        if total_fails >= self.MAX_TOTAL_FAILURES:
            return ToolGuardResult(
                allowed=False,
                reason="工具连续失败次数过多，请换个方式描述需求或稍后重试。",
                is_critical=True,
            )

        return ToolGuardResult(allowed=True)

    def record(self, tool_name: str, args: dict, success: bool) -> None:
        """工具执行后记录结果。"""
        self._history.append((tool_name, _hash_args(args), success))
        if len(self._history) > self._HISTORY_LIMIT:
            self._history = self._history[-self._HISTORY_LIMIT :]


def _hash_args(args: dict) -> str:
    """对参数字典做稳定哈希（取前 8 位）。"""
    raw = json.dumps(args, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.md5(raw).hexdigest()[:8]  # noqa: S324 – 非安全用途
