"""配置系统：config.json + .env 双层合并，按 key 访问。

加载顺序:
  1. config.json — 结构化默认配置（不存在则自动生成）
  2. .env — K=V 覆盖层（同名 key 以 .env 为准，独有 key 也加入）

使用方式:
  ```python
  from lumen_agent.config import get_settings, resolve_workspace_dir

  settings = get_settings()
  api_key = settings.get("DEEPSEEK_API_KEY")
  workspace = resolve_workspace_dir(settings)
  ```
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any

_PACKAGE_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _PACKAGE_DIR.parent
_CONFIG_JSON_PATH = _PACKAGE_DIR / "config.json"
_ENV_PATH = _PACKAGE_DIR / ".env"

logger = logging.getLogger(__name__)

# ── 默认配置 ─────────────────────────────────────────────────────
_DEFAULT_CONFIG: dict[str, Any] = {
    "_note": "LumenAgent 配置文件。同名 .env 变量会覆盖此文件的值。修改后重启生效。",
    "_version": "1.0",
    # ── DeepSeek ──
    "DEEPSEEK_API_KEY": "",
    "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
    "DEEPSEEK_MODEL": "deepseek-v4-flash",
    "DEEPSEEK_TEMPERATURE": None,
    "DEEPSEEK_MAX_TOKENS": None,
    "DEEPSEEK_TOP_P": None,
    "DEEPSEEK_ENABLE_THINKING": True,
    # ── 服务 ──
    "HOST": "127.0.0.1",
    "PORT": 8000,
    "RELOAD": False,
    "CORS_ORIGINS": "http://127.0.0.1:5173,http://localhost:5173",
    # ── 会话 ──
    "CONVERSATION_DB_PATH": "data/conversations.db",
    "CONVERSATION_MAX_CONTEXT_MESSAGES": 5,
    # ── 摘要窗口 ──
    "SUMMARY_THRESHOLD_TURNS": 6,
    "SUMMARY_COMPRESS_TURNS": 4,
    "SUMMARY_KEEP_TURNS": 2,
    # ── Embedding ──
    "EMBEDDING_API_KEY": "",
    "EMBEDDING_BASE_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings",
    "EMBEDDING_MODEL": "text-embedding-v4",
    # ── RAG / 知识库 ──
    "RAG_COLLECTION_NAME": "knowledge_base",
    "RAG_CHUNK_SIZE": 500,
    "RAG_CHUNK_OVERLAP": 150,
    "RAG_TOP_K": 5,
    "RAG_SIMILARITY_THRESHOLD": 0.2,
    "RAG_DISTANCE_METRIC": "cosine",
    "RAG_CHROMA_PATH": "data/chroma",
    # ── Agent ──
    "AGENT_MAX_TURNS": 20,
    "AGENT_MAX_TOOL_RESULT_CHARS": 20000,
    "AGENT_WORKSPACE_DIR": "work_space",
    "AGENT_TOOL_CHOICE": "auto",
    # ── 记忆检索 ──
    "MEMORY_SEARCH_TOP_K": 5,
    "MEMORY_SEARCH_SIMILARITY_THRESHOLD": 0.25,
    # ── Token / 上下文 ──
    "TOOL_RESULT_COMPRESS_TOKEN_LIMIT": 2000,
    "TOOL_RESULT_HEAD_TAIL_CHARS": 20,
    "CONTEXT_FORCE_COMPRESS_RATIO": 0.5,
    "DEFAULT_MODEL_CONTEXT_WINDOW": 131072,
    "MODEL_CONTEXT_WINDOWS": {
        "deepseek-v4-flash": 1_000_000,
        "deepseek-chat": 65_536,
        "deepseek-reasoner": 131_072,
    },
}


# ── 日志初始化（独立函数，不依赖 Settings） ──────────────────────

def log_config(*, enable_stream: bool = True) -> None:
    """初始化 logger：按天落盘 + 可选终端输出。"""
    _logger = logging.getLogger()
    _logger.setLevel(logging.INFO)
    _logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    _LOG_DIR = Path("log")
    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    file_handler = TimedRotatingFileHandler(
        filename=str(_LOG_DIR / "agent.log"),
        when="midnight",
        encoding="utf-8",
        backupCount=30,
    )
    file_handler.setFormatter(formatter)
    _logger.addHandler(file_handler)

    if enable_stream:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        _logger.addHandler(stream_handler)


# ── config.json 生成 ─────────────────────────────────────────────

def _ensure_config_json() -> bool:
    """若 config.json 不存在则生成默认文件。返回是否新创建。"""
    if _CONFIG_JSON_PATH.exists():
        return False
    _CONFIG_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_JSON_PATH.write_text(
        json.dumps(_DEFAULT_CONFIG, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("已生成默认配置文件：%s", _CONFIG_JSON_PATH)
    return True


# ── .env 解析 ────────────────────────────────────────────────────

def _parse_env_file(path: Path) -> dict[str, str]:
    """解析 .env 文件为 K=V 字典（跳过注释和空行）。"""
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        result[key.strip()] = value.strip()
    return result


def _coerce_type(value: str, existing: Any) -> Any:
    """尝试将 .env 字符串值转换为已有值的类型。"""
    if existing is None:
        return value
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
        # 复杂类型不能从 .env 单行覆盖，保留原值
        return existing
    return value


def _merge_env_into_config(config: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    """将 .env K=V 合并到 config 中。.env 同名 key 覆盖，独有 key 追加。"""
    merged = dict(config)
    for key, value in env.items():
        upper_key = key.upper()
        if upper_key in merged:
            merged[upper_key] = _coerce_type(value, merged[upper_key])
        else:
            merged[upper_key] = value
    return merged


# ── 计算型独立函数 ──────────────────────────────────────────────

def resolve_db_path(settings: "Settings") -> Path:
    """解析会话数据库的绝对路径。"""
    p = Path(settings.get("CONVERSATION_DB_PATH", "data/conversations.db"))
    return p if p.is_absolute() else _PACKAGE_DIR / p


def resolve_workspace_dir(settings: "Settings") -> Path:
    """解析工作空间的绝对路径。"""
    p = Path(settings.get("AGENT_WORKSPACE_DIR", "work_space"))
    return p if p.is_absolute() else _PROJECT_ROOT / p


def resolve_chroma_path(settings: "Settings") -> Path:
    """解析 Chroma 持久化目录的绝对路径。"""
    p = Path(settings.get("RAG_CHROMA_PATH", "data/chroma"))
    return p if p.is_absolute() else _PACKAGE_DIR / p


def resolve_cors_origins(settings: "Settings") -> list[str]:
    """解析 CORS 允许来源列表。"""
    raw = settings.get("CORS_ORIGINS", "")
    return [x.strip() for x in raw.split(",") if x.strip()]


def get_context_window(settings: "Settings", model_name: str) -> int:
    """返回指定模型的上下文窗口大小（token 数）。"""
    windows = settings.get("MODEL_CONTEXT_WINDOWS", {})
    if isinstance(windows, dict):
        return windows.get(model_name, settings.get("DEFAULT_MODEL_CONTEXT_WINDOW", 131072))
    return settings.get("DEFAULT_MODEL_CONTEXT_WINDOW", 131072)


# ── Settings 类 ─────────────────────────────────────────────────

class Settings:
    """Dict-like 配置容器：config.json + .env 合并，纯 key 访问。"""

    def __init__(self) -> None:
        self._data = self._load_and_merge()

    # ── 加载 ────────────────────────────────────────────────────

    @staticmethod
    def _load_and_merge() -> dict[str, Any]:
        """加载 config.json → .env 覆盖 → 返回合并结果。"""
        _ensure_config_json()

        # 1. 读 JSON
        try:
            config: dict[str, Any] = json.loads(_CONFIG_JSON_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("config.json 读取失败，回退到默认值: %s", exc)
            config = dict(_DEFAULT_CONFIG)

        # 2. 读 .env
        env_data = _parse_env_file(_ENV_PATH)

        # 3. 合并
        merged = _merge_env_into_config(config, env_data)

        # 4. 摘要窗口校验（仅 WARNING，不阻塞）
        compress = merged.get("SUMMARY_COMPRESS_TURNS")
        keep = merged.get("SUMMARY_KEEP_TURNS")
        threshold = merged.get("SUMMARY_THRESHOLD_TURNS")
        if compress is not None and keep is not None and threshold is not None:
            if compress + keep != threshold:
                logger.warning(
                    "摘要窗口参数配置异常: compress(%s) + keep(%s) != threshold(%s)，"
                    "请检查 config.json / .env",
                    compress, keep, threshold,
                )

        return merged

    # ── 访问 ────────────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """按 key 获取配置值（自动转大写，不区分大小写）。"""
        return self._data.get(key.upper(), default)

    def __contains__(self, key: str) -> bool:
        return key.upper() in self._data


# ── 导出工厂 ────────────────────────────────────────────────────

@lru_cache
def get_settings() -> Settings:
    """单例。修改配置后请调用 ``refresh_settings()`` 清缓存。"""
    return Settings()


def refresh_settings() -> None:
    """清除缓存，下次 ``get_settings()`` 返回新实例（热更新）。"""
    get_settings.cache_clear()
