"""模型适配器工厂与导出。"""

from __future__ import annotations

from lumen_agent.config import Settings
from lumen_agent.infrastructure.client.deepseek_client import DeepSeekHttpClient
from lumen_agent.model_adapters.base import ModelAdapter
from lumen_agent.model_adapters.deepseek import DeepSeekAdapter


def get_model_adapter(settings: Settings) -> ModelAdapter:
    """当前先固定返回 DeepSeek 适配器，后续再扩展多模型分支。"""
    return DeepSeekAdapter(DeepSeekHttpClient(settings))
