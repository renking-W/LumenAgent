"""AgentStreamExecutor：流式多轮工具调用循环（完全模型无关）。"""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from lumen_agent.agent.context import ContextManager, ToolExecutionGuard
from lumen_agent.agent.tools.base import BaseTool, ToolResult
from lumen_agent.agent.tools.registry import ToolRegistry
from lumen_agent.config import Settings
from lumen_agent.model_adapters.base import ModelAdapter

logger = logging.getLogger(__name__)


class AgentStreamExecutor:
    """流式 Agent 工具循环（完全模型无关）。

    职责：
    - 接收 ModelAdapter 和工具列表
    - 执行多轮 tool_use / tool_result 循环
    - yield 事件供 SSE 推送
    - 通过 ToolExecutionGuard 防无限循环
    - 通过 ContextManager 控制上下文长度

    done / continue 判断机制：
      工具结果追加至消息历史后再次调用 LLM。
      LLM 不再发起工具调用 → 直接输出文本 → yield ("done", text)
      LLM 继续调用工具     → 循环进入下一轮
    """

    def __init__(
        self,
        adapter: ModelAdapter,
        tools: list[BaseTool],
        settings: Settings,
        *,
        max_turns: int | None = None,
    ) -> None:
        self.adapter = adapter
        self.tools: dict[str, BaseTool] = {t.name: t for t in tools}
        self.tool_schemas: list[dict] = [t.to_internal_schema() for t in tools]
        self.max_turns = max_turns or settings.agent_max_turns

        self.context = ContextManager(
            max_turns=settings.summary_threshold_turns,
            max_tool_result_chars=settings.agent_max_tool_result_chars,
        )
        self.guard = ToolExecutionGuard()

    async def run_stream(
        self,
        messages: list[dict[str, Any]],
    ) -> AsyncIterator[tuple[str, str | dict]]:
        """主入口：启动工具循环，yield 事件流。

        yield (kind, data):
          ("content", str)                    – 文本增量
          ("reasoning_content", str)          – 思维链增量
          ("tool_calls", list[dict])          – 本轮模型发起的工具调用列表
          ("tool_execution_start", dict)      – 单个工具开始执行
          ("tool_execution_end", dict)        – 单个工具执行完毕
          ("done", str)                       – 最终回复（无工具调用时）
          ("error", str)                      – 错误
        """
        for turn in range(self.max_turns):
            logger.info(f"[Agent] 第 {turn + 1} 轮开始，当前消息数: {len(messages)}")

            # 上下文裁剪
            messages = self.context.trim_to_max_turns(messages)
            messages = self.context.truncate_tool_results(messages)

            tool_calls_this_turn: list[dict] = []
            full_content = ""
            full_reasoning = ""

            # ── 1. 流式调用模型  这里循环调用llm，直到llm返回一个done为止
            try:
                async for kind, data in self.adapter.chat_stream(
                    messages, tools=self.tool_schemas
                ):
                    if kind == "content":
                        full_content += data  # type: ignore[operator]
                        yield ("content", data)
                    elif kind == "reasoning_content":
                        full_reasoning += data  # type: ignore[operator]
                        yield ("reasoning_content", data)
                    elif kind == "tool_use":
                        tool_calls_this_turn.append(data)  # type: ignore[arg-type]
            except Exception as exc:
                logger.exception("[Agent] 模型调用异常")
                yield ("error", str(exc))
                return

            # ── 2. 将 assistant 响应追加到消息历史 ─────────────
            assistant_blocks: list[dict] = []
            if full_reasoning.strip():
                assistant_blocks.append(
                    {"type": "thinking", "thinking": full_reasoning}
                )
            if full_content:
                assistant_blocks.append({"type": "text", "text": full_content})
            for tc in tool_calls_this_turn:
                assistant_blocks.append(
                    {
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["name"],
                        "input": tc.get("input", {}),
                    }
                )
            messages.append({"role": "assistant", "content": assistant_blocks})

            # ── 3. 无工具调用 → 结束 ────────────────────────────
            if not tool_calls_this_turn:
                logger.info(f"[Agent] 第 {turn + 1} 轮无工具调用，循环结束")
                yield ("done", full_content)
                return

            # ── 4. 通知前端本轮工具列表 ─────────────────────────
            yield (
                "tool_calls",
                [{"name": tc["name"], "id": tc["id"]} for tc in tool_calls_this_turn],
            )

            # ── 5. 逐个执行工具 ──────────────────────────────────
            tool_result_blocks: list[dict] = []

            for tc in tool_calls_this_turn:
                tool_name = tc["name"]
                tool_input = tc.get("input", {})
                tool_id = tc["id"]

                # 防循环检查
                guard_result = self.guard.check(tool_name, tool_input)
                if not guard_result.allowed:
                    logger.warning(f"[Agent] Guard 拦截工具 '{tool_name}': {guard_result.reason}")
                    yield (
                        "tool_execution_start",
                        {"tool_call_id": tool_id, "name": tool_name, "arguments": tool_input},
                    )
                    yield (
                        "tool_execution_end",
                        {
                            "tool_call_id": tool_id,
                            "name": tool_name,
                            "status": "error",
                            "execution_time": 0.0,
                            "result_preview": guard_result.reason,
                        },
                    )
                    tool_result_blocks.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": guard_result.reason,
                            "is_error": True,
                        }
                    )
                    if guard_result.is_critical:
                        yield ("error", guard_result.reason)
                        return
                    continue

                # 正常执行
                yield (
                    "tool_execution_start",
                    {"tool_call_id": tool_id, "name": tool_name, "arguments": tool_input},
                )

                start_time = time.monotonic()
                result: ToolResult = await self._execute_tool(tool_name, tool_input)
                elapsed = time.monotonic() - start_time
                result.execution_time = elapsed

                self.guard.record(tool_name, tool_input, not result.is_error)

                result_preview = str(result.result)[:200] if result.result is not None else ""
                logger.info(
                    f"[Agent] 工具 '{tool_name}' 执行完成 "
                    f"status={result.status} elapsed={elapsed:.3f}s"
                )

                yield (
                    "tool_execution_end",
                    {
                        "tool_call_id": tool_id,
                        "name": tool_name,
                        "status": result.status,
                        "execution_time": elapsed,
                        "result_preview": result_preview,
                    },
                )

                tool_result_blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": str(result.result) if result.result is not None else "",
                        "is_error": result.is_error,
                    }
                )

            # ── 6. 将 tool_result 追加到消息历史，进入下一轮 ──────
            messages.append({"role": "user", "content": tool_result_blocks})

        # 超出 max_turns
        msg = f"已执行 {self.max_turns} 轮，达到最大步数限制，请重试。"
        logger.warning(f"[Agent] {msg}")
        yield ("error", msg)

    async def _execute_tool(self, name: str, params: dict) -> ToolResult:
        """执行单个工具，工具不存在时返回 error。"""
        tool = self.tools.get(name)
        if tool is None:
            available = list(self.tools.keys())
            return ToolResult.error(
                f"工具 '{name}' 不存在。可用工具: {available}"
            )
        try:
            return await tool.execute(params)
        except Exception as exc:
            logger.exception(f"[Agent] 工具 '{name}' 执行异常")
            return ToolResult.error(f"工具执行异常: {exc}")
