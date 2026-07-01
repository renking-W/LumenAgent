"""HTTP 客户端封装：DeepSeek、Ollama、Chroma、Embedding、MCP、Agnes。"""

from lumen_agent.model_adapters.client.agnes_client import AgnesHttpClient
from lumen_agent.model_adapters.client.deepseek_client import DeepSeekHttpClient
from lumen_agent.model_adapters.client.mcp_client import (
    MCPConnection,
    MCPStdioConnection,
    get_mcp_manager,
)
from lumen_agent.model_adapters.client.ollama_client import OllamaHttpClient
from lumen_agent.model_adapters.client.open_router_client import OpenRouterHttpClient
