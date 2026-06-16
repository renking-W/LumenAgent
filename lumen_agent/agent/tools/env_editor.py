"""环境配置编辑工具：通过 key 读写 config.json / .env 配置项。修改后自动热生效。"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from lumen_agent.agent.tools.base import BaseTool, ToolResult
from lumen_agent.agent.tools.registry import ToolRegistry

_PACKAGE_DIR = Path(__file__).resolve().parent.parent.parent
_CONFIG_JSON_PATH = _PACKAGE_DIR / "config.json"
_ENV_PATH = _PACKAGE_DIR / ".env"


@ToolRegistry.register
class EnvEditor(BaseTool):
    """读取或编辑系统配置（config.json + .env）。编辑 .env 后自动热更新，无需重启服务。"""

    _logger = logging.getLogger(__name__)

    name = "env_editor"
    description = "读取或编辑系统配置项。读取时展示合并结果（含来源）；设置时写入 .env（高优先级层）。修改后自动热生效。"
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["read", "set", "set_json"],
                "description": (
                    "操作类型：\n"
                    "- read：读取所有配置项（合并 config.json + .env，标注来源）\n"
                    "- set：修改指定配置项（写入 .env，热生效）\n"
                    "- set_json：修改 config.json 中的配置项（低优先级，重启生效）"
                ),
            },
            "key": {
                "type": "string",
                "description": "配置键名（大写，如 LLM_API_KEY），action=set/set_json 时必填。",
            },
            "value": {
                "type": "string",
                "description": "要设置的配置值，action=set/set_json 时必填。",
            },
        },
        "required": ["action"],
    }

    async def execute(self, params: dict) -> ToolResult:
        action = str(params.get("action", "read")).strip()

        if action == "read":
            return await self._read_config()

        if action in ("set", "set_json"):
            key = str(params.get("key", "")).strip().upper()
            value = str(params.get("value", "")).strip()
            if not key:
                return ToolResult.error("key 不能为空。")
            if not value:
                return ToolResult.error("value 不能为空。")
            return await self._write_key(key, value, target=action)

        return ToolResult.error(f"未知操作：{action}，仅支持 read / set / set_json。")

    # ── read ────────────────────────────────────────────────────

    async def _read_config(self) -> ToolResult:
        """读取合并配置并标注来源。"""
        config_data = self._load_json()
        env_data = self._parse_env()
        default_keys = {
            "LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL",
            "HOST", "PORT", "CORS_ORIGINS",
            "CONVERSATION_DB_PATH", "CONVERSATION_MAX_CONTEXT_MESSAGES",
            "SUMMARY_THRESHOLD_TURNS", "SUMMARY_COMPRESS_TURNS", "SUMMARY_KEEP_TURNS",
            "EMBEDDING_API_KEY", "EMBEDDING_BASE_URL", "EMBEDDING_MODEL",
            "RAG_COLLECTION_NAME", "RAG_CHUNK_SIZE", "RAG_CHUNK_OVERLAP",
            "RAG_TOP_K", "RAG_SIMILARITY_THRESHOLD", "RAG_DISTANCE_METRIC", "RAG_CHROMA_PATH",
            "AGENT_MAX_TURNS", "AGENT_MAX_TOOL_RESULT_CHARS", "AGENT_WORKSPACE_DIR", "AGENT_TOOL_CHOICE",
            "MEMORY_SEARCH_TOP_K", "MEMORY_SEARCH_SIMILARITY_THRESHOLD",
            "TOOL_RESULT_COMPRESS_TOKEN_LIMIT", "TOOL_RESULT_HEAD_TAIL_CHARS",
            "CONTEXT_FORCE_COMPRESS_RATIO", "DEFAULT_MODEL_CONTEXT_WINDOW",
            "MODEL_CONTEXT_WINDOWS",
        }
        # 合并所有 key
        all_keys = set(config_data.keys()) | set(env_data.keys()) | default_keys
        all_keys -= {"_note", "_version"}

        configs: list[dict[str, str]] = []
        for key in sorted(all_keys):
            json_val = config_data.get(key)
            env_val = env_data.get(key)

            if env_val is not None and json_val is not None and str(env_val) != str(json_val):
                # .env 覆盖了 JSON
                configs.append({
                    "key": key,
                    "value": str(env_val),
                    "source": ".env (overrides config.json)",
                })
            elif env_val is not None:
                configs.append({
                    "key": key,
                    "value": str(env_val),
                    "source": ".env",
                })
            elif json_val is not None:
                configs.append({
                    "key": key,
                    "value": str(json_val),
                    "source": "config.json",
                })
            else:
                configs.append({
                    "key": key,
                    "value": "",
                    "source": "default",
                })

        # 特殊处理：MODEL_CONTEXT_WINDOWS 展示友好格式
        for item in configs:
            if item["key"] == "MODEL_CONTEXT_WINDOWS":
                try:
                    obj = json.loads(item["value"]) if item["value"] else config_data.get("MODEL_CONTEXT_WINDOWS", {})
                    if isinstance(obj, dict):
                        item["value"] = json.dumps(obj, ensure_ascii=False)
                except (json.JSONDecodeError, TypeError):
                    pass

        self._logger.info("配置读取完成，共 %s 项", len(configs))
        return ToolResult.success({
            "action": "read",
            "configs": configs,
            "sources": {
                "config_json": str(_CONFIG_JSON_PATH),
                "env": str(_ENV_PATH),
            },
        })

    # ── write ───────────────────────────────────────────────────

    async def _write_key(self, key: str, value: str, target: str) -> ToolResult:
        """写入配置项到指定目标文件。"""
        if target == "set":
            return await self._write_env(key, value)
        return await self._write_json(key, value)

    async def _write_env(self, key: str, value: str) -> ToolResult:
        """修改 .env 文件中的配置项，写回后热更新。"""
        if not _ENV_PATH.exists():
            return ToolResult.error(f".env 文件不存在：{_ENV_PATH}")

        lines = _ENV_PATH.read_text(encoding="utf-8").splitlines()
        found = False
        new_lines: list[str] = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith(f"{key}="):
                new_lines.append(f"{key}={value}")
                found = True
                continue
            if stripped.startswith(f"#{key}="):
                new_lines.append(f"{key}={value}")
                found = True
                continue
            new_lines.append(line)

        if not found:
            new_lines.append(f"{key}={value}")

        _ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        self._logger.info(".env 配置已更新：%s=%s", key, value)

        # 热更新：清除配置缓存
        from lumen_agent.config import refresh_settings
        refresh_settings()
        self._logger.info("配置缓存已清除，新配置已生效")

        return ToolResult.success({
            "action": "set",
            "key": key,
            "value": value,
            "file": str(_ENV_PATH),
            "note": "写入 .env，已热生效（高优先级覆盖 config.json）",
        })

    async def _write_json(self, key: str, value: str) -> ToolResult:
        """修改 config.json 中的配置项。"""
        if not _CONFIG_JSON_PATH.exists():
            return ToolResult.error(f"config.json 文件不存在：{_CONFIG_JSON_PATH}")

        try:
            config = json.loads(_CONFIG_JSON_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            return ToolResult.error(f"config.json 读取失败：{exc}")

        # 尝试类型转换以保持 JSON 类型一致性
        existing = config.get(key)
        if existing is not None:
            typed_value = self._coerce_type(value, existing)
        else:
            typed_value = value

        config[key] = typed_value
        _CONFIG_JSON_PATH.write_text(
            json.dumps(config, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._logger.info("config.json 已更新：%s=%s", key, typed_value)

        return ToolResult.success({
            "action": "set_json",
            "key": key,
            "value": str(typed_value),
            "file": str(_CONFIG_JSON_PATH),
            "note": "写入 config.json（低优先级，.env 中的同名值会覆盖此项）",
        })

    # ── 加载辅助 ────────────────────────────────────────────────

    def _load_json(self) -> dict:
        """读取 config.json，失败时返回空 dict。"""
        if not _CONFIG_JSON_PATH.exists():
            return {}
        try:
            data = json.loads(_CONFIG_JSON_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def _parse_env(self) -> dict[str, str]:
        """解析 .env 文件为 K=V 字典。"""
        if not _ENV_PATH.exists():
            return {}
        result: dict[str, str] = {}
        for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" not in stripped:
                continue
            key, _, value = stripped.partition("=")
            result[key.strip()] = value.strip()
        return result

    @staticmethod
    def _coerce_type(value: str, existing: object) -> object:
        """尝试将字符串转换为已有值的类型。"""
        if isinstance(existing, bool):
            return value.lower() in ("true", "1", "yes")
        if isinstance(existing, int):
            try:
                return int(value)
            except ValueError:
                return value
        if isinstance(existing, float):
            try:
                return float(value)
            except ValueError:
                return value
        if isinstance(existing, dict):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                pass
            return existing
        return value
