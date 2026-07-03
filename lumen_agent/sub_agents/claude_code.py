"""Claude Code ACP 适配器。

通过 `npx -y @agentclientprotocol/claude-agent-acp` 启动 ACP bridge，
将 Anthropic Claude Code SDK 暴露为 ACP agent。
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from lumen_agent.sub_agents.base import AcpAgentAdapter
from lumen_agent.sub_agents.registry import SubAgentRegistry


@SubAgentRegistry.register
class ClaudeCodeAdapter(AcpAgentAdapter):
    """Claude Code (via @agentclientprotocol/claude-agent-acp) 的 ACP 适配器。"""

    @property
    def name(self) -> str:
        return "claude_code"

    @property
    def label(self) -> str:
        return "Claude Code"

    def spawn_command(self) -> list[str]:
        npx = self._resolve_npx()
        return [npx, "-y", "@agentclientprotocol/claude-agent-acp"]

    def spawn_env(self, base_env: dict[str, str], run_id: str, depth: int) -> dict[str, str]:
        env = super().spawn_env(base_env, run_id, depth)
        # 把 ANTHROPIC_API_KEY 透传（若父进程已设置则继承，否则从 Lumen 配置读取）
        if "ANTHROPIC_API_KEY" not in env:
            try:
                from lumen_agent.config import get_settings
                key = get_settings().get("ANTHROPIC_API_KEY", "")
                if key:
                    env["ANTHROPIC_API_KEY"] = key
            except Exception:
                pass
        # Windows: 确保 APPDATA 等变量存在（npx 需要）
        for k in ("APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "USERPROFILE", "HOME"):
            if k in base_env:
                env.setdefault(k, base_env[k])
        return env

    def is_available(self) -> bool:
        """npx 可用即视为可用（-y 会自动下载包）。"""
        return shutil.which("npx") is not None or shutil.which("npx.cmd") is not None

    def check_credentials(self, env: dict[str, str]) -> str | None:
        if not env.get("ANTHROPIC_API_KEY", "").strip():
            return (
                "未配置 ANTHROPIC_API_KEY。Claude Code 需要 Anthropic 官方 API Key，"
                "与 Lumen 主脑使用的 LLM_API_KEY（DeepSeek 等）不是同一个。"
                "请在 lumen_agent/config.json 或 .env 中设置 ANTHROPIC_API_KEY=sk-ant-..."
            )
        return None

    def availability_hint(self) -> str:
        return "请确保 Node.js (npm/npx) 已安装：https://nodejs.org"
