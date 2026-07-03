"""ACP Sub-Agent 适配器抽象基类。

每个适配器只需声明：
  - spawn_command(): 子进程启动命令
  - spawn_env(): 子进程环境变量（在 base_env 基础上追加 API key 等）
  - initial_session_config(): session/new 参数
  - supports_resume(): 是否支持续跑

SubAgentService 通过 AcpAgentAdapter 协议接口统一驱动所有适配器。
"""

from __future__ import annotations

import os
import platform
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class AcpAgentAdapter(ABC):
    """所有 ACP 编码 agent 适配器的抽象基类。"""

    # ── 子类声明 ──────────────────────────────────────────────────

    @property
    @abstractmethod
    def name(self) -> str:
        """适配器标识符（小写英文，如 'claude_code'）。"""

    @property
    @abstractmethod
    def label(self) -> str:
        """人类可读名称（如 'Claude Code'）。"""

    @abstractmethod
    def spawn_command(self) -> list[str]:
        """返回子进程启动命令（第一个元素为可执行文件名或路径）。

        Windows 下 npx 需要写成 ['npx.cmd', ...] 或通过 _resolve_npx() 处理。
        """

    def spawn_env(self, base_env: dict[str, str], run_id: str, depth: int) -> dict[str, str]:
        """返回子进程的环境变量字典。

        默认只追加 LUMEN_SUBAGENT_DEPTH，子类可 override 追加 API key 等。
        """
        env = dict(base_env)
        env["LUMEN_SUBAGENT_DEPTH"] = str(depth)
        env["LUMEN_RUN_ID"] = run_id
        return env

    def initial_session_config(
        self,
        cwd: Path,
        mcp_servers: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """返回 session/new 时的初始化参数字典。

        键对应 acp.Agent.new_session() 的参数（cwd、mcp_servers 等）。
        子类可 override 加入 additional_directories 等。
        """
        result: dict[str, Any] = {"cwd": str(cwd)}
        if mcp_servers:
            result["mcp_servers"] = mcp_servers
        return result

    def supports_resume(self) -> bool:
        """是否支持通过 load_session / resume_session 续跑。"""
        return True

    # ── 健康检查 ──────────────────────────────────────────────────

    def is_available(self) -> bool:
        """探测适配器所需的可执行文件是否存在。"""
        cmd = self.spawn_command()
        if not cmd:
            return False
        exe = cmd[0]
        # 忽略 .cmd 后缀尝试
        for candidate in [exe, exe.rstrip(".cmd")]:
            if shutil.which(candidate):
                return True
        return False

    def availability_hint(self) -> str:
        """不可用时给用户的安装提示。"""
        return f"请确保 {self.spawn_command()[0]} 已安装并在 PATH 中"

    def check_credentials(self, env: dict[str, str]) -> str | None:
        """启动前检查凭据是否齐全。返回 None 表示通过，否则返回错误说明。"""
        return None

    # ── 工具函数 ──────────────────────────────────────────────────

    @staticmethod
    def _resolve_npx() -> str:
        """返回平台适配的 npx 可执行路径（优先 which 解析的绝对路径）。"""
        for candidate in ("npx.cmd", "npx", "npx.exe"):
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
        return "npx.cmd" if platform.system() == "Windows" else "npx"

    @staticmethod
    def _env_or(key: str, default: str = "") -> str:
        """从当前进程环境变量取值，不存在时返回 default。"""
        return os.environ.get(key, default)
