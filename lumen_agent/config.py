"""环境变量 + 可选 `lumen_agent/.env`（字段名即 pydantic-settings 规则，如 `DEEPSEEK_API_KEY`）。"""
import logging
from functools import lru_cache
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PACKAGE_DIR = Path(__file__).resolve().parent
_DEFAULT_ENV_FILE = _PACKAGE_DIR / ".env"

def log_config():
    """初始化根 logger：按天落盘 + 日志级别。"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    # 配置 logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    # 格式
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    # 按天切分、持久化到文件
    file_handler = TimedRotatingFileHandler(
        filename="log/agent.log",  # 基础文件名
        when="midnight",  # 每天 0 点自动切分
        encoding="utf-8",
        backupCount=30  # 保留 30 天日志
    )
    file_handler.setFormatter(formatter)

    # 控制台输出
    # stream_handler = logging.StreamHandler()
    # stream_handler.setFormatter(formatter)

    # 全局生效
    logger.addHandler(file_handler)
    # logger.addHandler(stream_handler)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_DEFAULT_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # deepseek 相关配置
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    deepseek_temperature: float | None = None
    deepseek_max_tokens: int | None = None
    deepseek_top_p: float | None = None

    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    reload: bool = False

    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    # 会话 SQLite：相对路径基于包目录（`lumen_agent/`）
    conversation_db_path: str = "data/conversations.db"
    conversation_max_context_messages: int = Field(default=5, ge=1)

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


@lru_cache
def get_settings() -> Settings:
    """单例；单测改环境后需 `get_settings.cache_clear()`。"""
    return Settings()
