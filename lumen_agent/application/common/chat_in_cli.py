"""命令行对话：直调 Service 层，可选同时启动 HTTP 服务。

用法
----
    python -m lumen_agent.application.chat_in_cli       # 仅 CLI
    python -m lumen_agent.application.chat_in_cli --web  # CLI + Web

斜杠命令
--------
/exit    退出
/new     新建会话（重新生成 session_id）
"""

import asyncio
import logging
import threading
from uuid import uuid4
import questionary
from knowledge_in_cli import knowledge_operation
from lumen_agent.application.service.chat.chat_service import reply_with_agent
from lumen_agent.agent.tools import init_tools
from lumen_agent.config import get_settings, resolve_db_path
from lumen_agent.infrastructure.data_base.sqlite_conversation import SqliteConversationRepository
from lumen_agent.model_adapters import get_model_adapter


settings = get_settings()
repo = SqliteConversationRepository(resolve_db_path(settings))
llm = get_model_adapter(settings)


def _show_tool_event(kind: str, data: object) -> None:
    """展示工具调用/执行信息。"""
    if kind == "tool_calls":
        tools = data if isinstance(data, list) else []
        names = [t.get("name", "?") for t in tools]
        print(f"\n  ── 调用工具: {', '.join(names)} ──", flush=True)
    elif kind == "tool_result":
        info = data if isinstance(data, dict) else {}
        name = info.get("name", "?")
        status = info.get("status", "?")
        preview = info.get("result_preview", "")
        if status == "error":
            print(f"  ── 工具 [{name}] 失败: {preview[:80]}", flush=True)
        elif preview:
            print(f"  ── 工具 [{name}] 返回: {preview[:120]}", flush=True)


async def async_main() -> None:
    """交互式 CLI 主循环。"""
    init_tools()
    _logger = logging.getLogger(__name__)

    session_id = str(uuid4())
    print(f"会话 ID: {session_id}")
    print("输入 /exit 退出，/new 新建会话\n")

    while True:
        try:
            msg = input("You: ")
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not msg.strip():
            continue
        if msg.strip().lower() == "/exit":
            break
        if msg.strip().lower() == "/new":
            session_id = str(uuid4())
            print(f"新会话 ID: {session_id}")
            continue
        if msg.strip().lower() == "/knowledge":
            await knowledge_operation()

        _thinking = False      # 是否正在显示"思考中..."
        _has_prefix = False    # 是否已输出过"Assistant: "
        try:
            async for kind, data in reply_with_agent(
                repo, llm, session_id, 0, msg, settings
            ):
                match kind:
                    case "thinking":
                        if not _thinking:
                            print("Assistant: 思考中...", end="\r", flush=True)
                            _thinking = True
                            _has_prefix = True
                    case "text":
                        if _thinking:
                            print("\rAssistant: ", end="", flush=True)
                            _thinking = False
                        elif not _has_prefix:
                            # 没有 thinking 事件，首次内容前输出前缀
                            print("Assistant: ", end="", flush=True)
                            _has_prefix = True
                        print(data, end="", flush=True)
                    case "tool_calls" | "tool_use" | "tool_result":
                        if _thinking:
                            print("\r" + " " * 60 + "\r", end="", flush=True)
                            _thinking = False
                        _show_tool_event(kind, data)
                    case "done":
                        if _thinking:
                            print("\r" + " " * 60 + "\r", end="", flush=True)
                        print()
                    case "error":
                        if _thinking:
                            print("\rAssistant: ", end="", flush=True)
                            _thinking = False
                        elif not _has_prefix:
                            print("Assistant: ", end="", flush=True)
                            _has_prefix = True
                        print(f"[错误] {data}")
        except Exception as e:
            print(f"\n  [异常] {e}")
        finally:
            from lumen_agent.application.service.mcp.mcp_request_context import clear_allowed_server_ids
            clear_allowed_server_ids()

    print("再见！")


def main() -> None:
    """同步入口，供 pyproject.toml [project.scripts] 调用。"""
    from lumen_agent.config import log_config

    log_config(enable_stream=False)  # CLI 模式：日志只写文件，不输出终端

    from lumen_agent.app import run_uvicorn

    t = threading.Thread(target=run_uvicorn, daemon=True)
    t.start()

    asyncio.run(async_main())


if __name__ == "__main__":
    main()
