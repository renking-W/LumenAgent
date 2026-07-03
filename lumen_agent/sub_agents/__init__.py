"""Sub-Agent 编排层：通过 ACP (Agent Client Protocol) 调度本地编码 agent。"""

# 启动时预加载所有内置适配器，确保注册表不为空
from lumen_agent.sub_agents import claude_code  # noqa: F401
from lumen_agent.sub_agents import cursor_agent  # noqa: F401
from lumen_agent.sub_agents import codex  # noqa: F401
