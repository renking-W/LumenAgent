"""应用级配置：集中读取环境变量与可选 `.env` 文件。

设计目标（你可以把它类比成 Java/Spring Boot 的 `application.yml` + 环境覆盖）：
- **集中**：所有可调参数尽量从 `Settings` 读取，避免散落在各模块的 `os.getenv`。
- **类型与校验**：使用 Pydantic 字段类型、约束（例如端口范围）在启动阶段发现问题。
- **安全默认值**：敏感信息（API Key）默认空字符串，强制你在部署环境显式注入。

环境变量命名（pydantic-settings v2 默认规则）：
- 字段名 `deepseek_api_key` 对应环境变量 **`DEEPSEEK_API_KEY`**（大小写不敏感，常见写法大写）。
- 同理：`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`、`DEEPSEEK_TEMPERATURE`、`DEEPSEEK_MAX_TOKENS`、
  `DEEPSEEK_TOP_P`、`HOST`、`PORT`、`RELOAD`、`CORS_ORIGINS` 等。

`.env` 文件位置：
- 默认读取 `lumen_agent/.env`（与本文件同目录），文件不存在不会报错，只是完全依赖进程环境变量。

注意：
- **不要把真实密钥提交到 Git**。`.env` 应加入 `.gitignore`（若你尚未配置，请自行补充）。
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 本包在仓库中的物理目录：用于定位默认 `.env` 路径（相对路径稳定，不依赖进程 cwd）。
_PACKAGE_DIR = Path(__file__).resolve().parent
_DEFAULT_ENV_FILE = _PACKAGE_DIR / ".env"


class Settings(BaseSettings):
    """全局配置模型（一次解析，多处注入）。"""

    model_config = SettingsConfigDict(
        # 允许从 `.env` 读取；部署到 K8s 时通常用 Secret 注入环境变量，文件可能不存在。
        env_file=str(_DEFAULT_ENV_FILE),
        env_file_encoding="utf-8",
        # 忽略 `.env` 里未在模型声明的键，避免一点点多余配置就导致启动失败。
        extra="ignore",
    )

    # --- DeepSeek（对话 API，OpenAI Chat Completions 兼容）---
    # DeepSeek 文档一般提供 base_url + `/v1/chat/completions` 这种形态；此处只存 base_url。
    deepseek_api_key: str = Field(default="", description="DeepSeek API Key（Bearer Token）")
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com",
        description="OpenAI 兼容 Base URL，**不要**带尾斜杠（我们在客户端拼接路径）",
    )
    deepseek_model: str = Field(default="deepseek-chat", description="默认对话模型名（随供应商调整）")
    deepseek_temperature: float | None = Field(
        default=None,
        description="采样温度；None 表示请求体不传该字段，由上游使用默认策略。典型范围 0～2",
    )
    deepseek_max_tokens: int | None = Field(
        default=None,
        description="单次回复最大 token 上限；None 表示不传，由上游默认",
    )
    deepseek_top_p: float | None = Field(
        default=None,
        description="nucleus sampling；None 表示不传。典型范围 0～1",
    )

    # --- HTTP 服务（仅影响 `python -m lumen_agent.app` 这种内嵌启动；命令行 uvicorn 参数优先生效）---
    host: str = Field(default="127.0.0.1", description="bind 地址；容器内对公网监听常用 0.0.0.0")
    port: int = Field(default=8000, ge=1, le=65535, description="监听端口")
    reload: bool = Field(
        default=False,
        description="是否开启热重载（开发便利；生产应关闭，避免多进程/监控混乱）",
    )

    # --- CORS（独立前端开发时常用）---
    # 用逗号分隔字符串而不是 `list[str]`，是为了 `.env` 里一行写完，减少 JSON 转义心智负担。
    cors_origins: str = Field(
        default="http://127.0.0.1:5173,http://localhost:5173",
        description="允许的 Origin，逗号分隔；生产应收紧为明确域名列表",
    )

    @field_validator("deepseek_base_url")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        """统一去掉尾斜杠，避免拼接 URL 时出现 `//v1/...` 这种双斜杠边缘问题。"""
        return v.rstrip("/")

    @field_validator("deepseek_temperature")
    @classmethod
    def validate_temperature(cls, v: float | None) -> float | None:
        if v is None:
            return None
        if not 0.0 <= v <= 2.0:
            raise ValueError("deepseek_temperature must be between 0.0 and 2.0")
        return v

    @field_validator("deepseek_top_p")
    @classmethod
    def validate_top_p(cls, v: float | None) -> float | None:
        if v is None:
            return None
        if not 0.0 <= v <= 1.0:
            raise ValueError("deepseek_top_p must be between 0.0 and 1.0")
        return v

    @field_validator("deepseek_max_tokens")
    @classmethod
    def validate_max_tokens(cls, v: int | None) -> int | None:
        if v is None:
            return None
        if v < 1:
            raise ValueError("deepseek_max_tokens must be >= 1 when set")
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        """把 `cors_origins` 字符串解析成列表供 `CORSMiddleware` 使用。"""
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    """返回进程内单例 `Settings`（缓存解析结果）。

    为什么用 `@lru_cache`？
    - `Settings()` 解析环境变量/文件在冷启动时有一点成本；单例避免每个请求重复构造。
    - FastAPI 的 `Depends(get_settings)` 每次会调用函数，但 `lru_cache` 让后续调用极快。

    注意：
    - 单测若需要切换环境变量，记得 `get_settings.cache_clear()`，否则缓存会挡住新值。
    """
    return Settings()
