"""命令行对话：直调 Service 层，无需启动 HTTP 服务。

用法
----
    python -m lumen_agent.application.chat_in_cli

斜杠命令
--------
/exit    退出
/new     新建会话（重新生成 session_id）
"""

import asyncio
import logging
from uuid import uuid4

from lumen_agent.application.chat_service import reply_with_agent
from lumen_agent.agent.tools import init_tools
from lumen_agent.config import get_settings
from lumen_agent.infrastructure.sqlite_conversation import SqliteConversationRepository
from lumen_agent.model_adapters import get_model_adapter

settings = get_settings() #加载配置信息
repo = SqliteConversationRepository(settings.conversation_db_path_resolved()) #获得数据库对象
llm = get_model_adapter(settings) #获得模型适配器


def _show_tool_event(kind: str, data: object) -> None:
    """展示工具调用/执行信息。"""
    if kind == "tool_calls":
        tools = data if isinstance(data, list) else []
        names = [t.get("name", "?") for t in tools]
        print(f"\n  ── 调用工具: {', '.join(names)} ──", flush=True)
    elif kind == "tool_execution_end":
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
    logging.disable(logging.CRITICAL)  # 屏蔽后端 INFO 日志

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

        _thinking = False      # 是否正在显示"思考中..."
        _has_prefix = False    # 是否已输出过"Assistant: "
        try:
            async for kind, data in reply_with_agent(
                repo, llm, session_id, msg, settings
            ):
                match kind:
                    case "reasoning_content":
                        if not _thinking:
                            print("Assistant: 思考中...", end="\r", flush=True)
                            _thinking = True
                            _has_prefix = True
                    case "content":
                        if _thinking:
                            print("\rAssistant: ", end="", flush=True)
                            _thinking = False
                        elif not _has_prefix:
                            # 没有 thinking 事件，首次内容前输出前缀
                            print("Assistant: ", end="", flush=True)
                            _has_prefix = True
                        print(data, end="", flush=True)
                    case "tool_calls" | "tool_execution_start" | "tool_execution_end":
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

    print("再见！")


def main() -> None:
    """同步入口，供 pyproject.toml [project.scripts] 调用。"""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
