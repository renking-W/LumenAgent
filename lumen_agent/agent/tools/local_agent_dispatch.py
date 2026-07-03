"""local_agent_dispatch 工具：Lumen 主脑调度本地编码 agent 的统一入口。

支持的 actions：
  run        — 启动一个新的 sub-agent run
  answer     — 向挂起中的权限/提问请求回传决策
  stop       — 终止一个运行中的 run
  list_runs  — 列出历史 run（可按 parent_session_id / status 过滤）
  get_output — 获取指定 run 的完整输出
  list_agents — 列出可用的 agent 适配器（含可用性状态）
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from lumen_agent.agent.tools.base import BaseTool, ToolResult
from lumen_agent.agent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


@ToolRegistry.register
class LocalAgentDispatch(BaseTool):
    """调度本地编码 agent（Claude Code / Cursor / Codex）完成复杂编程任务。"""

    name = "local_agent_dispatch"
    description = (
        "调度本地 agent 执行复杂任务。\n"
        "actions:\n"
        "  run         — 启动 sub-agent，阻塞到第一个 checkpoint（permission_request 或完成）\n"
        "  answer      — 回复挂起的权限/问答请求，阻塞到下一个 checkpoint\n"
        "  stop        — 终止指定 run\n"
        "  list_runs   — 列出历史 run（可过滤）\n"
        "  get_output  — 获取指定 run 的完整输出\n"
        "  list_agents — 列出可用的 agent 适配器及可用性状态\n"
        "\n典型流程：先 run → 收到 asking 状态时用 answer 回复 → 最终收到 done 状态。"
    )
    requires_approval = True

    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["run", "answer", "stop", "list_runs", "get_output", "list_agents"],
                "description": "操作类型。必填",
            },
            # ── run 参数 ──────────────────────────────────────
            "agent_type": {
                "type": "string",
                "description": "agent 类型（如 'claude_code'）。action=run 时必填",
            },
            "prompt": {
                "type": "string",
                "description": "发给 sub-agent 的任务描述。action=run 时必填",
            },
            "cwd": {
                "type": "string",
                "description": "sub-agent 工作目录，默认为 Lumen 工作区目录。action=run 时可选",
            },
            "resume_run_id": {
                "type": "string",
                "description": "要续跑的历史 run_id（对应 ACP resume_session）。可选",
            },
            # ── answer 参数 ────────────────────────────────────
            "run_id": {
                "type": "string",
                "description": "目标 run 的 ID。action=answer/stop/get_output 时必填",
            },
            "decision": {
                "type": "string",
                "enum": ["allow_once", "allow_always", "deny", "answer"],
                "description": (
                    "授权决策。action=answer 时必填。"
                    "'answer' 表示开放式问答，配合 answer_text 使用。"
                ),
            },
            "option_id": {
                "type": "string",
                "description": "选择的 permission option ID（来自 asking 结果中的 options 列表）。可选",
            },
            "answer_text": {
                "type": "string",
                "description": "开放式问答的文字回复（decision=answer 时使用）。可选",
            },
            # ── list_runs 参数 ────────────────────────────────
            "status_filter": {
                "type": "string",
                "description": "按状态过滤：running / done / error / stopped。可选",
            },
        },
        "required": ["action"],
    }

    async def execute(self, params: dict) -> ToolResult:
        action = str(params.get("action", "")).strip()

        if action == "list_agents":
            return await self._list_agents()
        elif action == "run":
            return await self._action_run(params)
        elif action == "answer":
            return await self._action_answer(params)
        elif action == "stop":
            return await self._action_stop(params)
        elif action == "list_runs":
            return await self._action_list_runs(params)
        elif action == "get_output":
            return await self._action_get_output(params)
        else:
            return ToolResult.error(f"未知 action: {action}")

    # ── list_agents ────────────────────────────────────────────────

    async def _list_agents(self) -> ToolResult:
        from lumen_agent.sub_agents.registry import SubAgentRegistry
        agents = SubAgentRegistry.list_available()
        lines = ["可用的 Agent 适配器："]
        for a in agents:
            status = "✅ 可用" if a["available"] else f"❌ 不可用（{a['hint']}）"
            lines.append(f"  {a['name']} ({a['label']}): {status}")
        return ToolResult.success("\n".join(lines))

    # ── run ────────────────────────────────────────────────────────

    async def _action_run(self, params: dict) -> ToolResult:
        agent_type = str(params.get("agent_type", "")).strip()
        prompt = str(params.get("prompt", "")).strip()
        if not agent_type:
            return ToolResult.error("action=run 时 agent_type 必填")
        if not prompt:
            return ToolResult.error("action=run 时 prompt 必填")

        # 深度守卫
        depth_check = _check_depth()
        if depth_check:
            return ToolResult.error(depth_check)

        current_depth = int(os.environ.get("LUMEN_SUBAGENT_DEPTH", "0"))

        cwd_str = params.get("cwd")
        resume_run_id = params.get("resume_run_id")

        # 获取当前会话 ID（注入到 run 关联）
        parent_session_id = _current_session_id(params)

        # MCP 透传
        mcp_servers = await _load_mcp_servers()

        from lumen_agent.application.service.sub_agent_service import get_sub_agent_service
        from lumen_agent.config import get_settings

        service = get_sub_agent_service()
        try:
            handle = await service.start_run(
                agent_type=agent_type,
                prompt=prompt,
                cwd=cwd_str,
                parent_session_id=parent_session_id,
                resume_run_id=resume_run_id,
                mcp_servers=mcp_servers,
                depth=current_depth + 1,
            )
        except (ValueError, RuntimeError) as exc:
            return ToolResult.error(str(exc))

        # 阻塞到第一个 checkpoint
        settings = get_settings()
        run_timeout = float(settings.get("SUBAGENT_RUN_TIMEOUT", 600))
        handle = await service.wait_for_checkpoint(handle.run_id, timeout=run_timeout)
        return _handle_to_result(handle)

    # ── answer ──────────────────────────────────────────────────────

    async def _action_answer(self, params: dict) -> ToolResult:
        run_id = str(params.get("run_id", "")).strip()
        decision = str(params.get("decision", "")).strip()
        if not run_id:
            return ToolResult.error("action=answer 时 run_id 必填")
        if not decision:
            return ToolResult.error("action=answer 时 decision 必填")

        from lumen_agent.application.service.sub_agent_service import get_sub_agent_service
        from lumen_agent.config import get_settings

        service = get_sub_agent_service()
        try:
            await service.submit_answer(
                run_id=run_id,
                decision=decision,
                option_id=params.get("option_id"),
                answer_text=params.get("answer_text"),
            )
        except (KeyError, RuntimeError) as exc:
            return ToolResult.error(str(exc))

        # 阻塞到下一个 checkpoint
        settings = get_settings()
        perm_timeout = float(settings.get("SUBAGENT_PERMISSION_TIMEOUT", 300))
        handle = await service.wait_for_checkpoint(run_id, timeout=perm_timeout)
        return _handle_to_result(handle)

    # ── stop ────────────────────────────────────────────────────────

    async def _action_stop(self, params: dict) -> ToolResult:
        run_id = str(params.get("run_id", "")).strip()
        if not run_id:
            return ToolResult.error("action=stop 时 run_id 必填")
        from lumen_agent.application.service.sub_agent_service import get_sub_agent_service
        await get_sub_agent_service().stop_run(run_id)
        return ToolResult.success(f"run {run_id} 已发出停止信号")

    # ── list_runs ───────────────────────────────────────────────────

    async def _action_list_runs(self, params: dict) -> ToolResult:
        from lumen_agent.config import get_settings, resolve_db_path
        from lumen_agent.infrastructure.data_base.sqlite_sub_agent import SqliteSubAgentRepository
        settings = get_settings()
        repo = SqliteSubAgentRepository(resolve_db_path(settings))
        runs = await repo.list_runs(
            parent_session_id=params.get("parent_session_id"),
            status=params.get("status_filter"),
            limit=int(params.get("limit", 20)),
            offset=int(params.get("offset", 0)),
        )
        if not runs:
            return ToolResult.success("暂无 run 记录")
        lines = [f"共 {len(runs)} 条 run 记录："]
        for r in runs:
            lines.append(
                f"  [{r['status']}] {r['run_id']} | {r['agent_type']} | {r['created_at'][:19]}"
                f" | prompt: {r['prompt'][:60]}..."
            )
        return ToolResult.success("\n".join(lines))

    # ── get_output ──────────────────────────────────────────────────

    async def _action_get_output(self, params: dict) -> ToolResult:
        run_id = str(params.get("run_id", "")).strip()
        if not run_id:
            return ToolResult.error("action=get_output 时 run_id 必填")
        from lumen_agent.application.service.sub_agent_service import get_sub_agent_service
        service = get_sub_agent_service()
        handle = service.get_handle(run_id)
        if handle:
            output = "".join(handle.output_lines)
            return ToolResult.success(
                f"[run_id={run_id} status={handle.status}]\n{output or '(暂无输出)'}"
            )
        # 从 DB 读事件
        from lumen_agent.config import get_settings, resolve_db_path
        from lumen_agent.infrastructure.data_base.sqlite_sub_agent import SqliteSubAgentRepository
        repo = SqliteSubAgentRepository(resolve_db_path(get_settings()))
        events = await repo.list_events(run_id, limit=1000)
        texts = []
        for e in events:
            if e.get("event_type") == "session_update":
                t = e.get("payload", {}).get("text", "")
                if t:
                    texts.append(t)
        return ToolResult.success(
            f"[run_id={run_id} (历史)]\n{''.join(texts) or '(无输出记录)'}"
        )


# ── 辅助函数 ──────────────────────────────────────────────────────

def _check_depth() -> str | None:
    """若 LUMEN_SUBAGENT_DEPTH >= SUBAGENT_MAX_DEPTH，返回错误信息。"""
    try:
        from lumen_agent.config import get_settings
        max_depth = int(get_settings().get("SUBAGENT_MAX_DEPTH", 1))
        current = int(os.environ.get("LUMEN_SUBAGENT_DEPTH", "0"))
        if current >= max_depth:
            return (
                f"sub-agent 嵌套深度 ({current}) 已达上限 ({max_depth})，"
                "拒绝启动以防循环。"
            )
    except Exception:
        pass
    return None


def _current_session_id(params: dict) -> str:
    """尝试从当前执行上下文取 session_id（注入到 run 供关联查询）。"""
    return params.get("_session_id", "") or os.environ.get("LUMEN_SESSION_ID", "")


async def _load_mcp_servers() -> list[dict]:
    """从 DB 读取已启用的 MCP Server 配置，用于 ACP 透传。"""
    try:
        from lumen_agent.config import get_settings, resolve_db_path
        from lumen_agent.infrastructure.data_base.sqlite_mcp import SqliteMCPServerRepository
        from lumen_agent.infrastructure.data_base.sqlite_mcp_stdio import SqliteMCPStdioServerRepository
        settings = get_settings()
        db_path = resolve_db_path(settings)
        http_repo = SqliteMCPServerRepository(db_path)
        servers = await http_repo.list_enabled()
        return servers
    except Exception:
        return []


def _handle_to_result(handle) -> ToolResult:
    """把 RunHandle 的当前状态转成工具结果。"""
    if handle.status in ("done", "stopped", "error"):
        if handle.final_result:
            import json
            return ToolResult.success(json.dumps(handle.final_result, ensure_ascii=False))
        return ToolResult.success(
            f"run {handle.run_id} 已结束，状态={handle.status}"
        )
    elif handle.status == "asking":
        pending = handle.pending_permission
        if pending:
            import json
            result: dict = {
                "status": "asking",
                "kind": pending.kind,
                "run_id": handle.run_id,
                "options": pending.options,
                "tool_call": pending.tool_call,
            }
            if pending.question:
                result["question"] = pending.question
            return ToolResult.success(json.dumps(result, ensure_ascii=False))
    return ToolResult.success(
        f"run {handle.run_id} 状态={handle.status}（继续等待）"
    )
