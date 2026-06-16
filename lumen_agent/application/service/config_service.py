"""配置管理服务：config.json 的读取、写入、分类、类型转换等全部业务逻辑。"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from lumen_agent.api.schemas.config_dtos import (
    ConfigItemResponse,
    ConfigListResponse,
    UpdateConfigResponse,
)
from lumen_agent.config import refresh_settings

logger = logging.getLogger(__name__)

_PACKAGE_DIR = Path(__file__).resolve().parent.parent.parent
_CONFIG_JSON_PATH = _PACKAGE_DIR / "config.json"

# ── 系统保护键：前端不可见也不可编辑 ────────────────────────────
_SYSTEM_PROTECTED_KEYS: frozenset[str] = frozenset({
    "CONVERSATION_DB_PATH",
    "RAG_COLLECTION_NAME",
    "RAG_CHROMA_PATH",
    "AGENT_WORKSPACE_DIR",
    "MODEL_CONTEXT_WINDOWS",
    "DEFAULT_MODEL_CONTEXT_WINDOW",
    "HOST",
    "PORT",
    "RELOAD",
})

# ── 基础配置（固定集合） ────────────────────────────────────────
_BASIC_CONFIG_KEYS: frozenset[str] = frozenset({
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "LLM_MODEL",
    "EMBEDDING_API_KEY",
    "EMBEDDING_BASE_URL",
    "EMBEDDING_MODEL",
    "AGENT_MAX_TURNS",
})


# ── 文件 I/O ──────────────────────────────────────────────────

def _load_json() -> dict[str, Any]:
    """读取 config.json，失败时返回空 dict。"""
    if not _CONFIG_JSON_PATH.exists():
        return {}
    try:
        data = json.loads(_CONFIG_JSON_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        logger.warning("config.json 读取失败", exc_info=True)
        return {}


def _write_json(key: str, value: str) -> None:
    """写入 config.json：更新或追加键值对，保留 JSON 类型，写完后调用 refresh_settings()。"""
    config = _load_json()
    existing = config.get(key)
    typed_value = _coerce_type(value, existing) if existing is not None else value

    config[key] = typed_value
    _CONFIG_JSON_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    refresh_settings()
    logger.info("配置已写入 config.json 并热生效: %s=%s", key, typed_value)


# ── 类型转换 ──────────────────────────────────────────────────

def _coerce_type(value: str, existing: Any) -> Any:
    """尝试将字符串转换为已有值的类型，保持 JSON 类型一致。"""
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


# ── 分类辅助 ──────────────────────────────────────────────────

def _categorize(key: str) -> str:
    """返回 'basic' 或 'advanced'。"""
    return "basic" if key in _BASIC_CONFIG_KEYS else "advanced"


# ── 公开接口 ──────────────────────────────────────────────────

def list_configs() -> ConfigListResponse:
    """读取 config.json，返回按基础/高级分类的可编辑配置项列表。"""
    config = _load_json()
    basic: list[ConfigItemResponse] = []
    advanced: list[ConfigItemResponse] = []

    for key, value in config.items():
        if key.startswith("_"):
            continue
        if key in _SYSTEM_PROTECTED_KEYS:
            continue
        item = ConfigItemResponse(key=key, value=value, category=_categorize(key))
        (basic if item.category == "basic" else advanced).append(item)

    basic.sort(key=lambda x: x.key)
    advanced.sort(key=lambda x: x.key)

    return ConfigListResponse(basic=basic, advanced=advanced)


def update_config(key: str, value: str) -> UpdateConfigResponse:
    """更新配置项：校验 → 类型转换 → 写入 config.json → 热生效。

    Raises:
        ValueError: key 为空或为系统保护键。
    """
    if not key:
        raise ValueError("配置键名不能为空")

    if key in _SYSTEM_PROTECTED_KEYS:
        raise ValueError(f"'{key}' 是系统保护配置项，不允许修改")

    _write_json(key, value)

    return UpdateConfigResponse(
        status="ok",
        key=key,
        value=value,
        source="config.json",
        note="配置已写入 config.json 文件并热生效",
    )
