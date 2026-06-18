"""配置系统：config.json + .env 双层合并，按 key 访问。

加载顺序:
  1. config.json — 结构化默认配置（不存在则自动生成）
  2. .env — K=V 覆盖层（同名 key 以 .env 为准，独有 key 也加入）

使用方式:
  ```python
  from lumen_agent.config import get_settings, resolve_workspace_dir

  settings = get_settings()
  api_key = settings.get("LLM_API_KEY")
  workspace = resolve_workspace_dir(settings)
  ```
"""

from __future__ import annotations

import logging
from functools import lru_cache
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any

from lumen_agent.application.uitls.dir_guide import DirGuide
from lumen_agent.infrastructure.start_need.config_loader import load_and_merge

_PACKAGE_DIR = DirGuide.package_dir()
_PROJECT_ROOT = DirGuide.project_root()

logger = logging.getLogger(__name__)


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
        self._data = load_and_merge()

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
