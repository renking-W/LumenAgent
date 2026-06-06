""".env 配置文件编辑工具：读取/修改配置项，编辑后自动重置缓存使配置生效。"""

from __future__ import annotations

import logging
from pathlib import Path

from lumen_agent.agent.tools.base import BaseTool, ToolResult
from lumen_agent.agent.tools.registry import ToolRegistry

# .env 文件路径：lumen_agent/.env
_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


@ToolRegistry.register
class EnvEditor(BaseTool):
    """读取或编辑 .env 配置文件中的配置项。编辑后自动重新加载配置，无需重启服务。"""

    _logger = logging.getLogger(__name__)

    name = "env_editor"
    description = "读取或编辑 .env 配置文件中的配置项。编辑后自动重新加载配置，无需重启服务。"
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["read", "set"],
                "description": "操作类型：read 读取当前所有配置项，set 修改指定配置项。",
            },
            "key": {
                "type": "string",
                "description": "配置键名（大写，如 DEEPSEEK_API_KEY），action=set 时必填。",
            },
            "value": {
                "type": "string",
                "description": "要设置的配置值，action=set 时必填。",
            },
        },
        "required": ["action"],
    }

    async def execute(self, params: dict) -> ToolResult:
        action = str(params.get("action", "read")).strip()

        if action == "read":
            return self._read_env()

        if action == "set":
            key = str(params.get("key", "")).strip()
            value = str(params.get("value", "")).strip()
            if not key:
                return ToolResult.error("key 不能为空。")
            if not value:
                return ToolResult.error("value 不能为空。")
            return await self._set_env(key, value)

        return ToolResult.error(f"未知操作：{action}，仅支持 read / set。")

    def _read_env(self) -> ToolResult:
        """读取当前 .env 文件的所有有效配置项。"""
        if not _ENV_PATH.exists():
            return ToolResult.error(f".env 文件不存在：{_ENV_PATH}")

        lines = _ENV_PATH.read_text(encoding="utf-8").splitlines()
        configs: list[dict[str, str]] = []
        for line in lines:
            stripped = line.strip()
            # 跳过空行和纯注释行
            if not stripped or stripped.startswith("#"):
                continue
            if "=" not in stripped:
                continue
            # 允许值中包含 = 号
            key, _, value = stripped.partition("=")
            configs.append({"key": key.strip(), "value": value.strip()})

        self._logger.info(
            ".env 配置读取完成，共 %s 项有效配置", len(configs),
        )
        return ToolResult.success({
            "action": "read",
            "file_path": str(_ENV_PATH),
            "configs": configs,
        })

    async def _set_env(self, key: str, value: str) -> ToolResult:
        """修改指定配置项的值，写回文件后清除配置缓存。"""
        if not _ENV_PATH.exists():
            return ToolResult.error(f".env 文件不存在：{_ENV_PATH}")

        key_upper = key.upper()
        lines = _ENV_PATH.read_text(encoding="utf-8").splitlines()
        found = False

        new_lines: list[str] = []
        for line in lines:
            stripped = line.strip()

            # 匹配已激活的配置行 KEY=VALUE
            if stripped.startswith(f"{key_upper}="):
                new_lines.append(f"{key_upper}={value}")
                found = True
                continue

            # 匹配被注释的配置行 #KEY=VALUE → 改为激活状态
            if stripped.startswith(f"#{key_upper}="):
                new_lines.append(f"{key_upper}={value}")
                found = True
                continue

            # 其他行原样保留
            new_lines.append(line)

        # 文件中不存在该键 → 追加到末尾
        if not found:
            new_lines.append(f"{key_upper}={value}")

        _ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        self._logger.info(".env 配置已更新：%s=%s", key_upper, value)

        # ── 清除配置缓存，使新配置即时生效 ────────────────────────
        from lumen_agent.config import get_settings

        get_settings.cache_clear()
        self._logger.info("配置缓存已清除，下次调用将加载新配置")

        return ToolResult.success({
            "action": "set",
            "key": key_upper,
            "value": value,
            "file_path": str(_ENV_PATH),
        })
