"""SubAgentService：管理 sub-agent 运行生命周期的核心服务。

每个 run 有一个 RunHandle，内含：
  - ACP 子进程（通过 spawn_agent_process 启动）
  - ACP Agent 连接（ClientSideConnection）
  - PermissionBroker（接收 session/request_permission 并暂挂等待 Lumen 决策）
  - asyncio.Task（负责驱动 ACP prompt 并收集输出）

local_agent_dispatch 工具通过 start_run / submit_answer / stop_run 与此服务交互。
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import acp
from acp.schema import (
    AllowedOutcome,
    DeniedOutcome,
    PermissionOption,
    RequestPermissionResponse,
    SelectedPermissionOutcome,
)

from lumen_agent.infrastructure.sub_agent_event_bus import get_sub_agent_event_bus

logger = logging.getLogger(__name__)

# ── lumen_ask 约定 ───────────────────────────────────────────────
# sub-agent 调用一个不存在的命令 lumen_ask 来发起开放式提问
_LUMEN_ASK_MARKER = "lumen_ask"


# ── 挂起的权限请求 ────────────────────────────────────────────────

@dataclass
class PendingPermission:
    """一条挂起的权限/问答请求。"""

    pending_id: str
    run_id: str
    kind: str  # "permission" | "open_question"
    options: list[dict[str, Any]]
    tool_call: dict[str, Any]
    question: str | None  # 仅 open_question 时填
    # 结果 Future，SubAgentService.submit_answer() 时 set_result
    future: asyncio.Future[dict[str, Any]] = field(default_factory=asyncio.Future)


# ── RunHandle ─────────────────────────────────────────────────────

@dataclass
class RunHandle:
    """单次 sub-agent run 的运行时状态。"""

    run_id: str
    agent_type: str
    parent_session_id: str
    prompt_text: str
    cwd: Path
    acp_session_id: str = ""
    status: str = "starting"  # starting / running / asking / done / error / stopped
    stop_reason: str = ""
    # 累积输出（纯文本拼接，供 get_output 返回）
    output_lines: list[str] = field(default_factory=list)
    # 已修改文件路径列表
    modified_files: list[str] = field(default_factory=list)
    # 当前挂起的权限请求（最多同时一个）
    pending_permission: PendingPermission | None = None
    # 下一个 checkpoint 信号：run/answer 阻塞在此
    checkpoint_event: asyncio.Event = field(default_factory=asyncio.Event)
    # 关联的 asyncio Task（驱动 ACP 的后台协程）
    task: asyncio.Task | None = None
    # 子进程（用于级联 kill）
    process: Any = None
    # 最终结果
    final_result: dict[str, Any] | None = None


# ── LumenClient（ACP Client 侧实现） ─────────────────────────────

class LumenClient:
    """ACP Client 协议的实现：接收 sub-agent 的 session_update 和 permission 请求。

    每个 RunHandle 对应一个 LumenClient 实例。
    """

    def __init__(self, handle: RunHandle) -> None:
        self._handle = handle

    async def request_permission(
        self,
        options: list[PermissionOption],
        session_id: str,
        tool_call: Any,
        **kwargs: Any,
    ) -> RequestPermissionResponse:
        """sub-agent 请求授权（或通过 lumen_ask 发起开放式提问）。"""
        h = self._handle
        bus = get_sub_agent_event_bus()

        # 检测是否是 lumen_ask 开放式提问
        raw_input = None
        kind = "permission"
        question = None

        try:
            raw_input = tool_call.raw_input if hasattr(tool_call, "raw_input") else None
            title = tool_call.title if hasattr(tool_call, "title") else ""
            if (
                _LUMEN_ASK_MARKER in (title or "").lower()
                or _LUMEN_ASK_MARKER in str(raw_input or "").lower()
            ):
                kind = "open_question"
                question = str(raw_input or title or "sub-agent 提问")
        except Exception:
            pass

        tool_call_dict = {}
        try:
            tool_call_dict = tool_call.model_dump(by_alias=True) if hasattr(tool_call, "model_dump") else {}
        except Exception:
            pass

        opts_list = []
        try:
            opts_list = [o.model_dump(by_alias=True) for o in options]
        except Exception:
            opts_list = []

        pending_id = uuid.uuid4().hex[:12]
        pending = PendingPermission(
            pending_id=pending_id,
            run_id=h.run_id,
            kind=kind,
            options=opts_list,
            tool_call=tool_call_dict,
            question=question,
        )
        h.pending_permission = pending
        h.status = "asking"

        # 通知 EventBus（前端实时显示）
        event_payload: dict[str, Any] = {
            "type": "sub_agent_event",
            "event": "permission_request",
            "run_id": h.run_id,
            "pending_id": pending_id,
            "kind": kind,
            "options": opts_list,
            "tool_call": tool_call_dict,
        }
        if question:
            event_payload["question"] = question
        await bus.publish(h.run_id, event_payload)

        # 触发 checkpoint —— local_agent_dispatch 工具阻塞在此
        h.checkpoint_event.set()

        # 等待 Lumen LLM 的决策（由 submit_answer 唤醒）
        try:
            decision = await asyncio.wait_for(
                pending.future,
                timeout=_permission_timeout(),
            )
        except asyncio.TimeoutError:
            logger.warning("run=%s 权限请求超时，自动拒绝", h.run_id)
            decision = {"decision": "deny"}

        # 重置 checkpoint 信号
        h.checkpoint_event.clear()
        h.pending_permission = None
        h.status = "running"

        # 构造 ACP 响应
        decision_str = decision.get("decision", "deny")
        if decision_str in ("allow_once", "allow_always", "answer"):
            # 找到匹配的 option_id（选第一个 allow 类 option）
            option_id = decision.get("option_id", "")
            if not option_id and opts_list:
                option_id = opts_list[0].get("optionId", opts_list[0].get("option_id", "allow"))

            meta: dict[str, Any] | None = None
            if decision_str == "answer" and decision.get("answer_text"):
                meta = {"lumen_answer": decision["answer_text"]}

            return RequestPermissionResponse(
                outcome=AllowedOutcome(
                    outcome="selected",
                    option_id=option_id,
                    field_meta=meta,
                )
            )
        else:
            return RequestPermissionResponse(
                outcome=DeniedOutcome(outcome="cancelled")
            )

    async def session_update(
        self,
        session_id: str,
        update: Any,
        **kwargs: Any,
    ) -> None:
        """接收流式输出（tokens、tool_call 状态、plan 更新等）。"""
        h = self._handle
        bus = get_sub_agent_event_bus()

        update_dict: dict[str, Any] = {}
        text: str = ""

        try:
            update_dict = update.model_dump(by_alias=True) if hasattr(update, "model_dump") else {}
            # 尝试提取文本内容
            if hasattr(update, "text"):
                text = update.text or ""
            elif hasattr(update, "delta"):
                text = str(update.delta or "")
        except Exception:
            pass

        if text:
            h.output_lines.append(text)

        # 检测文件变更
        try:
            locs = update_dict.get("locations") or []
            for loc in locs:
                p = loc.get("path") if isinstance(loc, dict) else None
                if p and p not in h.modified_files:
                    h.modified_files.append(p)
        except Exception:
            pass

        # 发布到 EventBus
        payload: dict[str, Any] = {
            "type": "sub_agent_event",
            "event": "session_update",
            "run_id": h.run_id,
            "update": update_dict,
        }
        if text:
            payload["text"] = text
        await bus.publish(h.run_id, payload)

    async def write_text_file(self, content: str, path: str, session_id: str, **kwargs: Any):
        """sub-agent 写文件时记录路径。"""
        from acp.schema import WriteTextFileResponse
        if path and path not in self._handle.modified_files:
            self._handle.modified_files.append(path)
        await get_sub_agent_event_bus().publish(self._handle.run_id, {
            "type": "sub_agent_event",
            "event": "write_file",
            "run_id": self._handle.run_id,
            "path": path,
        })
        return WriteTextFileResponse()

    async def read_text_file(self, path: str, session_id: str, limit=None, line=None, **kwargs: Any):
        """sub-agent 读文件时转发实际文件内容。"""
        from acp.schema import ReadTextFileResponse
        try:
            content = Path(path).read_text(encoding="utf-8")
            if limit is not None:
                lines = content.splitlines()
                start = (line or 1) - 1
                content = "\n".join(lines[start: start + limit])
        except Exception as exc:
            content = f"[读取失败: {exc}]"
        return ReadTextFileResponse(content=content)

    def on_connect(self, conn: Any) -> None:
        pass


# ── SubAgentService ───────────────────────────────────────────────

class SubAgentService:
    """管理所有 sub-agent 运行的核心服务（应用全局单例）。"""

    def __init__(self) -> None:
        self._runs: dict[str, RunHandle] = {}
        self._lock = asyncio.Lock()

    # ── 启动 run ──────────────────────────────────────────────────

    async def start_run(
        self,
        *,
        agent_type: str,
        prompt: str,
        cwd: str | Path | None = None,
        parent_session_id: str = "",
        resume_run_id: str | None = None,
        mcp_servers: list[dict[str, Any]] | None = None,
        depth: int = 0,
    ) -> RunHandle:
        """启动一个新的 sub-agent run，返回 RunHandle（此时 run 已在后台执行）。"""
        from lumen_agent.sub_agents.registry import SubAgentRegistry
        from lumen_agent.config import get_settings, resolve_workspace_dir
        from lumen_agent.application.uitls.dir_guide import DirGuide

        adapter = SubAgentRegistry.get(agent_type)
        if adapter is None:
            raise ValueError(f"未知的 agent_type: {agent_type}")
        if not adapter.is_available():
            raise RuntimeError(f"{adapter.label} 不可用：{adapter.availability_hint()}")

        # 启动前检查 API Key 等凭据
        probe_env = adapter.spawn_env(dict(os.environ), "probe", depth + 1)
        cred_err = adapter.check_credentials(probe_env)
        if cred_err:
            raise RuntimeError(cred_err)

        run_id = f"run-{uuid.uuid4().hex[:12]}"
        resolved_cwd = Path(cwd) if cwd else DirGuide.workspace_dir()

        h = RunHandle(
            run_id=run_id,
            agent_type=agent_type,
            parent_session_id=parent_session_id,
            prompt_text=prompt,
            cwd=resolved_cwd,
        )

        async with self._lock:
            self._runs[run_id] = h

        # 持久化
        await self._persist_create(h)

        # 启动后台驱动协程
        h.task = asyncio.create_task(
            self._run_agent(h, adapter, prompt, resume_run_id, mcp_servers, depth),
            name=f"sub_agent.{run_id}",
        )

        return h

    async def _run_agent(
        self,
        h: RunHandle,
        adapter: Any,
        prompt: str,
        resume_run_id: str | None,
        mcp_servers: list[dict[str, Any]] | None,
        depth: int,
    ) -> None:
        """后台协程：驱动整个 ACP 会话，直到结束或出错。"""
        bus = get_sub_agent_event_bus()

        try:
            base_env = dict(os.environ)
            env = adapter.spawn_env(base_env, h.run_id, depth)
            cmd = adapter.spawn_command()

            client = LumenClient(h)

            # 注入 lumen_ask 提示到 prompt 前缀
            full_prompt = _inject_lumen_ask_hint(prompt)

            async with acp.spawn_agent_process(
                client,
                cmd[0], *cmd[1:],
                env=env,
                cwd=str(h.cwd),
            ) as (conn, proc):
                h.process = proc
                h.status = "running"

                await bus.publish(h.run_id, {
                    "type": "sub_agent_event",
                    "event": "started",
                    "run_id": h.run_id,
                    "agent_type": h.agent_type,
                })

                # initialize + authenticate
                await conn.initialize(protocol_version=acp.PROTOCOL_VERSION)

                # 认证（claude-agent-acp 用 anthropic-api-key 方法）
                if h.agent_type == "claude_code":
                    await conn.authenticate(method_id="anthropic-api-key")
                else:
                    try:
                        await conn.authenticate(method_id="anthropic-api-key")
                    except Exception as auth_exc:
                        logger.warning("run=%s 认证跳过或失败: %s", h.run_id, auth_exc)

                # 构造 MCP servers 参数
                acp_mcp_servers = _build_mcp_servers(mcp_servers)

                # new_session 或 resume_session
                if resume_run_id:
                    prev = self._runs.get(resume_run_id)
                    prev_session_id = prev.acp_session_id if prev else ""
                    if prev_session_id:
                        try:
                            session_resp = await conn.resume_session(
                                cwd=str(h.cwd),
                                session_id=prev_session_id,
                                mcp_servers=acp_mcp_servers or None,
                            )
                            h.acp_session_id = session_resp.session_id
                        except Exception:
                            session_resp = await conn.new_session(
                                cwd=str(h.cwd),
                                mcp_servers=acp_mcp_servers or None,
                            )
                            h.acp_session_id = session_resp.session_id
                    else:
                        session_resp = await conn.new_session(
                            cwd=str(h.cwd),
                            mcp_servers=acp_mcp_servers or None,
                        )
                        h.acp_session_id = session_resp.session_id
                else:
                    session_resp = await conn.new_session(
                        cwd=str(h.cwd),
                        mcp_servers=acp_mcp_servers or None,
                    )
                    h.acp_session_id = session_resp.session_id

                await self._persist_update(h.run_id, {"acp_session_id": h.acp_session_id})

                # 发送 prompt
                prompt_resp = await conn.prompt(
                    prompt=[acp.text_block(full_prompt)],
                    session_id=h.acp_session_id,
                )

                # prompt_resp 中止理由
                stop_reason = "end_turn"
                try:
                    stop_reason = prompt_resp.stop_reason or "end_turn"
                except Exception:
                    pass

                h.stop_reason = str(stop_reason)
                h.status = "done"
                h.final_result = {
                    "status": "done",
                    "output": "".join(h.output_lines),
                    "modified_files": h.modified_files,
                    "stop_reason": h.stop_reason,
                    "run_id": h.run_id,
                }

        except asyncio.CancelledError:
            h.status = "stopped"
            h.stop_reason = "cancelled"
            h.final_result = {
                "status": "stopped",
                "output": "".join(h.output_lines),
                "modified_files": h.modified_files,
                "stop_reason": "cancelled",
                "run_id": h.run_id,
            }
        except Exception as exc:
            logger.exception("run=%s 异常: %s", h.run_id, exc)
            h.status = "error"
            h.stop_reason = str(exc)
            h.final_result = {
                "status": "error",
                "error": str(exc),
                "output": "".join(h.output_lines),
                "run_id": h.run_id,
            }
        finally:
            await bus.publish(h.run_id, {
                "type": "sub_agent_event",
                "event": "finished",
                "run_id": h.run_id,
                "status": h.status,
                "stop_reason": h.stop_reason,
            })
            await self._persist_update(h.run_id, {
                "status": h.status,
                "stop_reason": h.stop_reason,
                "finished_at": _iso_now(),
            })
            # 唤醒任何还在等待 checkpoint 的调用者
            h.checkpoint_event.set()

    # ── 提交答复 ──────────────────────────────────────────────────

    async def submit_answer(
        self,
        run_id: str,
        decision: str,
        option_id: str | None = None,
        answer_text: str | None = None,
    ) -> None:
        """把 Lumen LLM 的决策回传给等待中的 PermissionBroker。"""
        h = self._runs.get(run_id)
        if h is None:
            raise KeyError(f"run {run_id} 不存在")
        if h.pending_permission is None:
            raise RuntimeError(f"run {run_id} 没有挂起的权限请求")

        decision_payload: dict[str, Any] = {
            "decision": decision,
        }
        if option_id:
            decision_payload["option_id"] = option_id
        if answer_text:
            decision_payload["answer_text"] = answer_text

        h.pending_permission.future.set_result(decision_payload)

    # ── 停止 run ──────────────────────────────────────────────────

    async def stop_run(self, run_id: str) -> None:
        """级联终止 sub-agent 子进程。"""
        h = self._runs.get(run_id)
        if h is None:
            return
        if h.task and not h.task.done():
            h.task.cancel()
        if h.process is not None:
            try:
                h.process.kill()
            except Exception:
                pass
        h.status = "stopped"
        h.stop_reason = "user_stop"
        h.checkpoint_event.set()
        await self._persist_update(run_id, {
            "status": "stopped",
            "stop_reason": "user_stop",
            "finished_at": _iso_now(),
        })

    # ── 查询 ──────────────────────────────────────────────────────

    def get_handle(self, run_id: str) -> RunHandle | None:
        return self._runs.get(run_id)

    async def wait_for_checkpoint(
        self, run_id: str, timeout: float | None = None
    ) -> RunHandle:
        """阻塞直到 run 达到下一个 checkpoint（permission_request 或 done/error）。"""
        h = self._runs.get(run_id)
        if h is None:
            raise KeyError(f"run {run_id} 不存在")
        try:
            await asyncio.wait_for(h.checkpoint_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            pass
        return h

    # ── 持久化帮助 ────────────────────────────────────────────────

    async def _persist_create(self, h: RunHandle) -> None:
        try:
            from lumen_agent.config import get_settings, resolve_db_path
            from lumen_agent.infrastructure.data_base.sqlite_sub_agent import SqliteSubAgentRepository
            db_path = resolve_db_path(get_settings())
            repo = SqliteSubAgentRepository(db_path)
            await repo.create_run({
                "run_id": h.run_id,
                "parent_session_id": h.parent_session_id,
                "agent_type": h.agent_type,
                "prompt": h.prompt_text,
                "cwd": str(h.cwd),
            })
        except Exception as exc:
            logger.warning("run=%s 持久化创建失败: %s", h.run_id, exc)

    async def _persist_update(self, run_id: str, updates: dict[str, Any]) -> None:
        try:
            from lumen_agent.config import get_settings, resolve_db_path
            from lumen_agent.infrastructure.data_base.sqlite_sub_agent import SqliteSubAgentRepository
            db_path = resolve_db_path(get_settings())
            repo = SqliteSubAgentRepository(db_path)
            await repo.update_run(run_id, updates)
        except Exception as exc:
            logger.warning("run=%s 持久化更新失败: %s", run_id, updates)

    async def append_event(self, run_id: str, event_type: str, payload: dict[str, Any]) -> None:
        try:
            from lumen_agent.config import get_settings, resolve_db_path
            from lumen_agent.infrastructure.data_base.sqlite_sub_agent import SqliteSubAgentRepository
            db_path = resolve_db_path(get_settings())
            repo = SqliteSubAgentRepository(db_path)
            await repo.append_event(run_id, event_type, payload)
        except Exception as exc:
            logger.warning("run=%s 事件记录失败: %s", run_id, exc)


# ── 辅助函数 ──────────────────────────────────────────────────────

def _inject_lumen_ask_hint(prompt: str) -> str:
    hint = (
        "\n\n[系统指引] 当你需要向主脑 Lumen 询问方向性/开放性问题时，"
        f"请调用虚拟命令 `{_LUMEN_ASK_MARKER} <你的问题>`，"
        "这会触发权限请求；主脑会以文本形式回复你，请把回复作为决策依据继续工作。\n"
    )
    return prompt + hint


def _build_mcp_servers(mcp_servers: list[dict[str, Any]] | None) -> list[Any]:
    """把 Lumen MCP server 配置转换为 ACP 能识别的格式。"""
    if not mcp_servers:
        return []
    result = []
    for s in mcp_servers:
        url = s.get("url", "")
        if not url:
            continue
        transport = s.get("transport", "sse")
        try:
            if transport == "streamable_http":
                from acp.schema import HttpMcpServer
                result.append(HttpMcpServer(url=url))
            else:
                from acp.schema import SseMcpServer
                result.append(SseMcpServer(url=url))
        except Exception:
            pass
    return result


def _permission_timeout() -> float:
    try:
        from lumen_agent.config import get_settings
        return float(get_settings().get("SUBAGENT_PERMISSION_TIMEOUT", 300))
    except Exception:
        return 300.0


def _iso_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# ── 全局单例 ──────────────────────────────────────────────────────

_service: SubAgentService | None = None


def get_sub_agent_service() -> SubAgentService:
    global _service
    if _service is None:
        _service = SubAgentService()
    return _service
