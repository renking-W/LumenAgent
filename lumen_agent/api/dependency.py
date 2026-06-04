"""FastAPI `Depends` 工厂：集中装配模型适配器与仓储。"""

from fastapi import Depends

from lumen_agent.config import Settings, get_settings
from lumen_agent.infrastructure.data_base.sqlite_conversation import SqliteConversationRepository
from lumen_agent.model_adapters import get_model_adapter
from lumen_agent.model_adapters.base import ModelAdapter


def get_llm_client(settings: Settings = Depends(get_settings)) -> ModelAdapter:
    """注入模型适配器（当前返回 DeepSeek）。"""
    return get_model_adapter(settings)


def get_conversation_repo(settings: Settings = Depends(get_settings)) -> SqliteConversationRepository:
    """注入 SQLite 会话仓储（路径由 Settings 解析）。"""
    return SqliteConversationRepository(settings.conversation_db_path_resolved())
