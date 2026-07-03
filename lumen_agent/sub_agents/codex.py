"""OpenAI Codex ACP 适配器。

通过 `npx -y @agentclientprotocol/codex-acp` 启动 ACP bridge。
"""

from __future__ import annotations

import shutil

from lumen_agent.sub_agents.base import AcpAgentAdapter
from lumen_agent.sub_agents.registry import SubAgentRegistry


@SubAgentRegistry.register
class CodexAdapter(AcpAgentAdapter):
    """OpenAI Codex (via @agentclientprotocol/codex-acp) 的 ACP 适配器。"""

    @property
    def name(self) -> str:
        return "codex"

    @property
    def label(self) -> str:
        return "OpenAI Codex"

    def spawn_command(self) -> list[str]:
        npx = self._resolve_npx()
        return [npx, "-y", "@agentclientprotocol/codex-acp"]

    def spawn_env(self, base_env: dict, run_id: str, depth: int) -> dict:
        env = super().spawn_env(base_env, run_id, depth)
        if "OPENAI_API_KEY" not in env:
            try:
                from lumen_agent.config import get_settings
                key = get_settings().get("OPENAI_API_KEY", "")
                if key:
                    env["OPENAI_API_KEY"] = key
            except Exception:
                pass
        for k in ("APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "USERPROFILE", "HOME"):
            if k in base_env:
                env.setdefault(k, base_env[k])
        return env

    def is_available(self) -> bool:
        return shutil.which("npx") is not None or shutil.which("npx.cmd") is not None

    def check_credentials(self, env: dict[str, str]) -> str | None:
        if not env.get("OPENAI_API_KEY", "").strip():
            return "未配置 OPENAI_API_KEY。Codex 需要 OpenAI API Key。"
        return None

    def availability_hint(self) -> str:
        return "请确保 Node.js (npm/npx) 已安装：https://nodejs.org"
