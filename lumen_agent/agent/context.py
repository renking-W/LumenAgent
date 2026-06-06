"""Agent 运行时上下文管理：轮次裁剪、tool_result 截断、防无限循环保护。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

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


# ──────────────────────────────────────────────
# 纯函数：工具消息压缩 & 轮次切片
# ──────────────────────────────────────────────

def compress_tool_blocks(
    messages: list[dict],
    counter: "Any",
    *,
    tool_result_token_limit: int = 2000,
    head_tail_chars: int = 20,
) -> list[dict]:
    """遍历消息列表，仅对超长 ``tool_result.content`` 做截断压缩（原地修改）。

    压缩规则：
    - 若 counter.count(content) > tool_result_token_limit
      → content = content[:head_tail_chars] + "……" + content[-head_tail_chars:]
    - tool_use 及其他字段（type / id / name / input / is_error / tool_use_id 等）全部原样保留。
    - text / thinking 块不做任何修改。

    注意：传入的 ``messages`` 会被原地修改。调用方无需预先深拷贝——
    上层 ``turns_to_messages()`` 每次返回新列表，无外部引用。
    """
    for msg in messages:
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") != "tool_result":
                continue
            raw = block.get("content")
            if not isinstance(raw, str) or not raw:
                continue
            if counter.count(raw) > tool_result_token_limit:
                block["content"] = raw[:head_tail_chars] + "……" + raw[-head_tail_chars:]
    return messages


def extract_complete_turns(messages: list[dict]) -> list[list[dict]]:
    """将消息列表按 user 消息切分为完整轮次列表。

    tool_result 已嵌入 assistant 消息内部，不再作为独立 user 消息出现，
    因此每个 user 都是真实用户输入，直接作为轮次起点。
    """
    turns: list[list[dict]] = []
    current: list[dict] = []

    for msg in messages:
        if msg.get("role") == "user":
            if current:
                turns.append(current)
            current = [msg]
        else:
            current.append(msg)

    if current:
        turns.append(current)

    return turns


def turns_to_messages(turns: list[list[dict]]) -> list[dict]:
    """将轮次列表展平回消息列表。"""
    return [msg for turn in turns for msg in turn]
