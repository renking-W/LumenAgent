"""环境变量 + 可选 `lumen_agent/.env`（字段名即 pydantic-settings 规则，如 `DEEPSEEK_API_KEY`）。"""
import logging
from functools import lru_cache
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PACKAGE_DIR = Path(__file__).resolve().parent
_DEFAULT_ENV_FILE = _PACKAGE_DIR / ".env"

def log_config(*, enable_stream: bool = True):
    """初始化 logger：按天落盘 + 可选终端输出。"""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    # 避免重复初始化时 handler 堆积
    logger.handlers.clear()

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
    logger.addHandler(file_handler)

    if enable_stream:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_DEFAULT_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # deepseek 相关配置
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_temperature: float | None = None
    deepseek_max_tokens: int | None = None
    deepseek_top_p: float | None = None
    # None = 不传该字段（由模型默认行为决定）；True/False = 显式开关思考模式
    deepseek_enable_thinking: bool | None = None

    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    reload: bool = False

    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173,http://localhost:8080"

    # 会话 SQLite：相对路径基于包目录（`lumen_agent/`）
    conversation_db_path: str = "data/conversations.db"
    conversation_max_context_messages: int = Field(default=5, ge=1)

    # 滑动窗口摘要：默认每 6 轮触发，前 4 轮压缩、后 2 轮保留为原文进入下一窗口
    summary_threshold_turns: int = Field(default=6, ge=2)
    summary_compress_turns: int = Field(default=4, ge=1)
    summary_keep_turns: int = Field(default=2, ge=1)

    # Agent 工具循环配置
    agent_max_turns: int = Field(default=20, ge=1, le=100)
    agent_max_tool_result_chars: int = Field(default=20000, ge=1000)
    agent_workspace_dir: str = "workspace"
    web_search_api_key: str = ""

    # Agent 工具调用策略：auto / none / required / force_<tool_name>
    agent_tool_choice: str = Field(default="auto", pattern=r"^(auto|none|required|force_.+)$")

    # 知识库 / RAG
    # embedding_api_key：阿里云 Embedding 接口的鉴权密钥，和 deepseek_api_key 一样从 .env 读取。
    embedding_api_key: str = ""
    # embedding_base_url：阿里云兼容 OpenAI 的 Embedding 网关地址，默认指向 DashScope 兼容模式。
    embedding_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings"
    # embedding_model：向量化使用的模型名，当前要求固定为 text-embedding-v4。
    embedding_model: str = "text-embedding-v4"
    # rag_collection_name：Chroma 里的 collection 名称，用于区分不同知识库集合。
    rag_collection_name: str = "knowledge_base"
    # rag_chunk_size：切分文本时单个 chunk 的目标长度，单位为字符。
    rag_chunk_size: int = Field(default=500, ge=100)
    # rag_chunk_overlap：相邻 chunk 的重叠字符数，用于减少语义断裂。
    rag_chunk_overlap: int = Field(default=150, ge=0)
    # rag_top_k：每次检索最多返回多少个 chunk。
    rag_top_k: int = Field(default=5, ge=1, le=50)
    # rag_similarity_threshold：检索结果的相似度过滤阈值，低于该值的 chunk 会被丢弃。
    rag_similarity_threshold: float = Field(default=0.2, ge=0.0, le=1.0)
    # rag_distance_metric：Chroma 使用的距离度量，默认 cosine。
    rag_distance_metric: str = "cosine"
    # rag_chroma_path：Chroma 持久化目录，默认相对 lumen_agent/ 解析到 data/chroma。
    rag_chroma_path: str = "data/chroma"

    # ── Token 预算 & 上下文窗口 ─────────────────────────────────────────────
    # 每个模型的上下文窗口（token 数），键为模型名，缺省时用 default_model_context_window
    model_context_windows: dict[str, int] = Field(
        default={
            "deepseek-v4-flash": 1_000_000,   # 约等于1M
            "deepseek-chat": 65_536,         # 64K
            "deepseek-reasoner": 131_072,    # 128K
        }   
    )
    default_model_context_window: int = Field(default=131_072, ge=1024)

    # 强制压缩阈值（占窗口比例）；超过此比例触发 force_compress_now
    context_force_compress_ratio: float = Field(default=0.5, gt=0.0, lt=1.0)

    # 单个 tool_result.content 压缩阈值（token 数）
    tool_result_compress_token_limit: int = Field(default=2000, ge=100)
    # 压缩后保留的头尾字符数
    tool_result_head_tail_chars: int = Field(default=20, ge=5)

    @field_validator("deepseek_base_url")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        """去掉 Base URL 尾斜杠，避免拼接路径出现双斜杠。"""
        return v.rstrip("/")

    @field_validator("deepseek_temperature")
    @classmethod
    def validate_temperature(cls, v: float | None) -> float | None:
        """采样温度范围 0～2；None 表示不传该字段。"""
        if v is None:
            return None
        if not 0.0 <= v <= 2.0:
            raise ValueError("deepseek_temperature must be between 0.0 and 2.0")
        return v

    @field_validator("deepseek_top_p")
    @classmethod
    def validate_top_p(cls, v: float | None) -> float | None:
        """top_p 范围 0～1；None 表示不传。"""
        if v is None:
            return None
        if not 0.0 <= v <= 1.0:
            raise ValueError("deepseek_top_p must be between 0.0 and 1.0")
        return v

    @field_validator("deepseek_max_tokens")
    @classmethod
    def validate_max_tokens(cls, v: int | None) -> int | None:
        """max_tokens 若设置须 >= 1。"""
        if v is None:
            return None
        if v < 1:
            raise ValueError("deepseek_max_tokens must be >= 1 when set")
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        """将逗号分隔的 CORS 字符串解析为列表。"""
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

    def conversation_db_path_resolved(self) -> Path:
        """会话库路径：相对路径时相对包目录解析为绝对路径。"""
        p = Path(self.conversation_db_path)
        if not p.is_absolute():
            p = _PACKAGE_DIR / p
        return p

    def context_window_for(self, model_name: str) -> int:
        """返回指定模型的上下文窗口大小（token 数）。未配置时返回默认值。"""
        return self.model_context_windows.get(model_name, self.default_model_context_window)

    def workspace_dir_resolved(self) -> Path:
        """工具默认工作区：相对路径时相对包目录解析为绝对路径。"""
        p = Path(self.agent_workspace_dir)
        if not p.is_absolute():
            p = _PACKAGE_DIR / p
        return p.resolve()

    def rag_chroma_path_resolved(self) -> Path:
        """Chroma 持久化目录：相对路径时相对包目录解析为绝对路径。"""
        p = Path(self.rag_chroma_path)
        if not p.is_absolute():
            p = _PACKAGE_DIR / p
        return p.resolve()

    @model_validator(mode="after")
    def _check_summary_window(self) -> "Settings":
        """启动期校验：compress + keep == threshold，避免窗口算法错位。"""
        if self.summary_compress_turns + self.summary_keep_turns != self.summary_threshold_turns:
            raise ValueError(
                "summary_compress_turns + summary_keep_turns must equal summary_threshold_turns"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """单例；单测改环境后需 `get_settings.cache_clear()`。"""
    return Settings()
