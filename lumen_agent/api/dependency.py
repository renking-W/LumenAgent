"""FastAPI `Depends` 工厂：集中装配 LLM 客户端等。"""

from fastapi import Depends

from lumen_agent.config import Settings, get_settings
from lumen_agent.infrastructure.deepseek_client import DeepSeekHttpClient
from lumen_agent.infrastructure.sqlite_conversation import SqliteConversationRepository


def get_llm_client(settings: Settings = Depends(get_settings)) -> DeepSeekHttpClient:
    """注入 DeepSeek HTTP 客户端（每请求新建，配置来自 Settings）。"""
    return DeepSeekHttpClient(settings)


def get_conversation_repo(settings: Settings = Depends(get_settings)) -> SqliteConversationRepository:
    """注入 SQLite 会话仓储（路径由 Settings 解析）。"""
    return SqliteConversationRepository(settings.conversation_db_path_resolved())
