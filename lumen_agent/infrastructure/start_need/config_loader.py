"""配置加载器：读取 config.json + .env 并合并为字典。

只负责 IO 和合并，不涉及业务逻辑。供 ``config.py`` 中的 ``Settings`` 类调用。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from lumen_agent.application.uitls.dir_guide import DirGuide

logger = logging.getLogger(__name__)

# ── 路径定位 ───────────────────────────────────────────────────
_CONFIG_JSON_PATH = DirGuide.config_json_path()
_ENV_PATH = DirGuide.env_path()

# ── 默认配置 ─────────────────────────────────────────────────────
_DEFAULT_CONFIG: dict[str, Any] = {
    "_note": "LumenAgent 配置文件。同名 .env 变量会覆盖此文件的值。修改后重启生效。",
    "_version": "1.0",
    # ── LLM ──
    "LLM_PROVIDER": "deepseek",
    "LLM_API_KEY": "",
    "LLM_BASE_URL": "https://api.deepseek.com",
    "LLM_MODEL": "deepseek-v4-flash",
    "LLM_TEMPERATURE": None,
    "LLM_MAX_TOKENS": None,
    "LLM_TOP_P": None,
    "LLM_ENABLE_THINKING": True,
    # ── 服务 ──
    "HOST": "127.0.0.1",
    "PORT": 21675,
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
    "TOOL_APPROVAL_MODE": "none",
    "TOOL_APPROVAL_TIMEOUT": 300,
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
        # ── Ollama / 常见开源模型 ──
        "llama3": 8_192,
        "llama3.1": 131_072,
        "llama3.2": 131_072,
        "mistral": 32_768,
        "qwen2": 131_072,
        "qwen2.5": 131_072,
        "deepseek-r1": 131_072,
        # ── OpenRouter / 常见云端模型 ──
        "gpt-4o": 128_000,
        "gpt-4o-mini": 128_000,
        "claude-sonnet-4-6": 200_000,
        "gemini-2.0-flash": 1_000_000,
        "llama-3.3-70b": 128_000,
        # ── Agnes ──
        "agnes-2.0-flash": 524_288,
    },
    # ── 调度器 ──
    "SCHEDULER_ENABLED": True,
    "SCHEDULER_TIMEZONE": "Asia/Shanghai",
    "SCHEDULER_DEFAULT_MAX_INSTANCES": 1,
    "SCHEDULER_COALESCE": True,
    # ── 系统清理任务保留天数（默认 30 天） ──
    "SCHEDULER_RETAIN_SESSION_DAYS": 30,
    "SCHEDULER_RETAIN_MEMORY_DAYS": 30,
    "SCHEDULER_RETAIN_EXECUTION_DAYS": 30,
    "SCHEDULER_RETAIN_LOG_DAYS" : 7,
    # ── 白名单IP ────
    "ALLOW_IP_ADDRESS": "127.0.0.1",
    # ── VM / SSH ──
    "VM_SSH_TIMEOUT": 60,
    "VM_SSH_BANNER_TIMEOUT": 60,
    "VM_SSH_KEEPALIVE": 40,
    "VM_EXECUTE_TIMEOUT": 30,
    "VM_DANGEROUS_COMMANDS": "rm -rf,shutdown,reboot,poweroff,init 0,init 6,dd if=,mkfs,fdisk,> /dev/sd,chmod 777 /",
    "VM_APPROVAL_MODE": "dangerous",
}


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


# ── 公开的加载入口 ───────────────────────────────────────────────

def load_and_merge() -> dict[str, Any]:
    """完整加载链：确保 config.json → 读取 → .env 覆盖 → 返回合并结果。"""
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
