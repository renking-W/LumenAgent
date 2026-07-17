"""模型适配器工厂与导出。"""

from __future__ import annotations

from lumen_agent.config import Settings
from lumen_agent.model_adapters.client import DeepSeekHttpClient
from lumen_agent.model_adapters.base import ModelAdapter
from lumen_agent.model_adapters.deepseek import DeepSeekAdapter


def get_model_adapter(settings: Settings) -> ModelAdapter:
    """根据 ``LLM_PROVIDER`` 配置返回对应的适配器。"""
    provider = settings.get("LLM_PROVIDER", "deepseek")
    if provider == "ollama":
        from lumen_agent.model_adapters.client.ollama_client import OllamaHttpClient
        from lumen_agent.model_adapters.ollama import OllamaAdapter

        return OllamaAdapter(OllamaHttpClient(settings))
    if provider == "openrouter":
        from lumen_agent.model_adapters.client.open_router_client import OpenRouterHttpClient
        from lumen_agent.model_adapters.open_router import OpenRouterAdapter

        return OpenRouterAdapter(OpenRouterHttpClient(settings))
    if provider == "openai":
        from lumen_agent.model_adapters.client.openai_responses_client import (
            OpenAIResponsesHttpClient,
        )
        from lumen_agent.model_adapters.openai import OpenAIAdapter

        return OpenAIAdapter(OpenAIResponsesHttpClient(settings))

    if provider == "agnes":
        from lumen_agent.model_adapters.client.agnes_client import AgnesHttpClient
        from lumen_agent.model_adapters.agnes import AgnesAdapter

        return AgnesAdapter(AgnesHttpClient(settings))
    return DeepSeekAdapter(DeepSeekHttpClient(settings))
