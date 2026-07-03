"""Cursor Agent ACP 适配器。

通过 `agent acp` 或 `cursor-agent acp` 启动 ACP bridge（Cursor CLI 内置）。
"""

from __future__ import annotations

import shutil

from lumen_agent.sub_agents.base import AcpAgentAdapter
from lumen_agent.sub_agents.registry import SubAgentRegistry


@SubAgentRegistry.register
class CursorAgentAdapter(AcpAgentAdapter):
    """Cursor Agent (via `agent acp`) 的 ACP 适配器。"""

    @property
    def name(self) -> str:
        return "cursor_agent"

    @property
    def label(self) -> str:
        return "Cursor Agent"

    def spawn_command(self) -> list[str]:
        # 优先使用 `agent`（新版 Cursor CLI），回退到 `cursor-agent`（老版）
        for cmd in ("agent", "cursor-agent"):
            if shutil.which(cmd):
                return [cmd, "acp"]
        return ["agent", "acp"]

    def spawn_env(self, base_env: dict, run_id: str, depth: int) -> dict:
        env = super().spawn_env(base_env, run_id, depth)
        # 透传 CURSOR_API_KEY（若已在环境中配置）
        if "CURSOR_API_KEY" not in env:
            try:
                from lumen_agent.config import get_settings
                key = get_settings().get("CURSOR_API_KEY", "")
                if key:
                    env["CURSOR_API_KEY"] = key
            except Exception:
                pass
        return env

    def is_available(self) -> bool:
        return shutil.which("agent") is not None or shutil.which("cursor-agent") is not None

    def availability_hint(self) -> str:
        return (
            "请安装 Cursor CLI 并确保 `agent acp` 可用：https://docs.cursor.com/agent/acp"
        )
