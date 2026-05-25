"""系统提示词构造器：按固定顺序组装各子系统的 system 提示词。"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path

from lumen_agent.agent.memory.memory_utils import MemoryFileUtils
from lumen_agent.agent.skills.meta import SkillMeta
from lumen_agent.agent.tools.base import BaseTool
from lumen_agent.infrastructure.sqlite_knowledge import SqliteKnowledgeRepository

_SECTION_SEP = "\n\n---\n\n"
_PROMPT_DOCS_DIR = Path(__file__).resolve().parent / "docs"
_MEMORY_UTILS = MemoryFileUtils.from_prompt_docs_path(_PROMPT_DOCS_DIR)


def _read_knowledge_index() -> list[dict]:
    """读取知识库索引文件，返回 file_name/source 的映射列表。"""
    index_path = Path(__file__).resolve().parent.parent.parent / "data" / "chroma" / "knowledge_index.json"
    if not index_path.exists():
        return []
    raw = index_path.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _read_knowledge_documents() -> list[dict]:
    """读取 SQLite 知识库中的所有文档元信息，用于 system prompt 展示。"""
    repo = SqliteKnowledgeRepository(Path(__file__).resolve().parent.parent.parent / "data" / "knowledge.db")
    try:
        return asyncio.run(repo.list_documents())
    except RuntimeError:
        return []
    except Exception:
        return []


def _render_tool(tool: BaseTool) -> str:
    """将单个 BaseTool 实例渲染为 Markdown 工具描述块。"""
    lines: list[str] = [f"### {tool.name}", "", tool.description, ""]
    props: dict = tool.parameters.get("properties", {})
    required: list[str] = tool.parameters.get("required", [])

    if props:
        lines.append("**参数：**")
        for param_name, param_schema in props.items():
            param_type = param_schema.get("type", "any")
            param_desc = param_schema.get("description", "")
            required_label = "必填" if param_name in required else "可选"
            lines.append(f"- `{param_name}`（{param_type}，{required_label}）：{param_desc}")

    return "\n".join(lines)


class SystemPromptBuilder:
    """链式系统提示词构造器。"""

    def __init__(self) -> None:
        self._sections: list[str] = []

    # ------------------------------------------------------------------ #
    # 1. 工具系统                                                          #
    # ------------------------------------------------------------------ #

    def add_tool_system(self, tools: list[BaseTool]) -> "SystemPromptBuilder":
        """将工具列表渲染为工具系统说明并追加到提示词。"""
        if not tools:
            return self
        tool_blocks = _SECTION_SEP.join(_render_tool(t) for t in tools)
        self._sections.append("# 工具系统\n\n你可以调用以下工具：\n\n" + _SECTION_SEP + tool_blocks)
        return self

    # ------------------------------------------------------------------ #
    # 2. 技能系统
    # ------------------------------------------------------------------ #

    def add_skill_system(self, skills: list[SkillMeta]) -> "SystemPromptBuilder":
        """将技能列表渲染为技能系统说明并追加到提示词。"""
        if not skills:
            return self

        available = [s for s in skills if s.available]
        unavailable = [s for s in skills if not s.available]

        lines: list[str] = [
            "# 技能系统",
            "",
            "以下是可供调用的技能列表（仅展示元信息）。",
            "",
            "> **重要约束**：调用任何技能前，**必须先使用 `read` 工具读取该技能的 SKILL.md 完整内容**，再按其中说明执行操作。本节只提供技能的名称、描述与文件路径，不会自动传入任何参数。如果没有技能明确适用：不要读取任何 SKILL.md，直接使用通用工具。",
        ]
        if available:
            lines += ["", "## 可使用的技能", ""]
            for s in available:
                prefix = f"{s.emoji} " if s.emoji else ""
                lines.append(f"- {prefix}**{s.name}** — {s.description}")
                lines.append(f"  path: `{s.path}`")
        if unavailable:
            lines += ["", "## 不可使用的技能（环境变量未配置）", ""]
            for s in unavailable:
                prefix = f"{s.emoji} " if s.emoji else ""
                missing = ", ".join(s.missing_envs)
                lines.append(f"- {prefix}**{s.name}** — {s.description}")
                lines.append(f"  path: `{s.path}`")
                lines.append(f"  缺失环境变量: `{missing}`")
        self._sections.append("\n".join(lines))
        return self

    # ------------------------------------------------------------------ #
    # 3. 记忆系统
    # ------------------------------------------------------------------ #
    def add_memory_system(self) -> "SystemPromptBuilder":
        """记忆系统：显式指导 LLM 主动维护长期记忆。"""
        lines = [
            "# 记忆系统",
            "",
            "当你遇到十分重要且可长期复用的信息时，必须主动编辑 `MEMORY.md`。",
            "",
            "## 应主动写入的内容",
            "- 用户习惯、偏好、禁忌",
            "- 用户明确认可的长期决策",
            "- 多次失败但值得保留的操作经验",
                "- 长期稳定的人物、项目、流程上下文",
            "",
            "## 写入原则",
            "- 只写长期有效的信息，不要记录短暂的闲聊。",
            "- 遇到重要信息时，优先考虑追加、归纳或去重，而不是重复堆叠。",
            "- 如果现有内容已经包含相同事实，应优先合并更新。",
            "- `MEMORY.md` 是长期记忆索引，保持精简、准确、可持续维护。",
            "- 使用`write`工具来对`MEMORY.md`文件进行编辑",
        ]
        self._sections.append("\n".join(lines))
        return self
        
    # ------------------------------------------------------------------ #
    # 4. 知识系统
    # ------------------------------------------------------------------ #
    
    def add_knowledge_system(self) -> "SystemPromptBuilder":
        """知识系统：只说明何时调用知识工具、如何使用结果，不拼接检索正文。"""
        knowledge_items = _read_knowledge_index()
        lines = [
            "# 知识系统",
            "",
            "当你需要查询项目知识库、配置说明、已入库文档或历史资料时，优先考虑调用 `knowledge_search`。",
            "",
            "## 当前知识库文件列表",
        ]
        if knowledge_items:
            for item in knowledge_items:
                lines.append(f"- `{item.get('file_name') or '未知文件'}`（来源：`{item.get('source') or '未知来源'}`）")
        else:
            lines.append("- 当前没有可用的知识库文件。")
        lines.extend([
            "",
            "## 调用原则",
            "- 当你遇到自己不知道不明确的问题或者定义、内容时，就可以去检索知识完善你的上下文。",
            "- 调用前先把用户问题整理成简洁、明确的检索 query。",
            "- 如果一次检索结果不足以支持回答，可以基于已有结果再次检索，但避免重复无效查询。",
            "",
            "## 使用方式",
            "- `knowledge_search` 负责具体检索逻辑，并返回标准化 `tool_result`。",
            "- 你必须把工具返回的 chunk、来源、相似度等信息当作检索依据，而不是把它当作最终答案。",
            "- 拿到结果后，先判断是否足够；足够则基于结果作答，不足则继续检索或明确说明信息不足。",
            "",
            "## 当前 SQLite 知识库文档",
        ])

        documents = _read_knowledge_documents()
        if documents:
            for doc in documents:
                lines.append(
                    f"- `{doc.get('file_name') or '未知文件'}`（来源：`{doc.get('source_name') or '未知来源'}`，状态：`{doc.get('status') or 'unknown'}`，chunks：{doc.get('chunk_count')}，更新于：`{doc.get('updated_at') or '未知时间'}`）"
                )
        else:
            lines.append("- 当前没有可用的 SQLite 知识库文档。")
        lines.extend([
            "",
            "## 输出要求",
            "- 作答时尽量引用检索到的来源信息。",
            "- 不要编造知识库中不存在的内容。",
            "- 如果没有命中足够相关的 chunk，明确告知用户未检索到可用结果。",
        ])
        self._sections.append("\n".join(lines))
        return self

    # --------------------------------
    # 5. 工作空间
    # --------------------------------
    def add_workspace(self) -> "SystemPromptBuilder":
        """工作空间：直接读取 RULE.md 并拼接到上下文中。"""
        rule_text = _MEMORY_UTILS.read_text_if_exists(_PROMPT_DOCS_DIR / "RULE.md")
        if rule_text:
            self._sections.append(rule_text)
        return self

    # ------------------------------------------------------------------ #
    # 6. 用户信息
    # ------------------------------------------------------------------ #
    def add_user_identity(self) -> "SystemPromptBuilder":
        user_text = _MEMORY_UTILS.read_text_if_exists(_PROMPT_DOCS_DIR / "USER.md")
        if user_text:
            self._sections.append(user_text)
        return self
    
    # ------------------------------------------------------------------ #
    # 7. 系统上下文
    # ------------------------------------------------------------------ #
    def add_project_context(self) -> "SystemPromptBuilder":
        me_text = _MEMORY_UTILS.read_text_if_exists(_PROMPT_DOCS_DIR / "ME.md")
        memory_path = _MEMORY_UTILS.memory_file_path()
        # 长期记忆文件
        memory_text = _MEMORY_UTILS.read_text_if_exists(memory_path)

        sections: list[str] = []
        if me_text:
            sections.append(me_text)
        if memory_text:
            sections.append(memory_text)

        if sections:
            self._sections.append(_SECTION_SEP.join(sections))
        return self

    # ------------------------------------------------------------------ #
    # 8. 运行时信息
    # ------------------------------------------------------------------ #
    def add_runtime_info(self) -> "SystemPromptBuilder":
        now_text = datetime.now().astimezone().isoformat(timespec="seconds")
        self._sections.append(f"# 系统时钟\n\n当前系统时间：`{now_text}`")
        return self

    def build(self) -> str:
        return _SECTION_SEP.join(self._sections)


def build_system_prompt(
    tools: list[BaseTool],
    skills: list[SkillMeta] | None = None,
) -> str:
    """工厂函数：按规范顺序组装系统提示词，返回完整 system 字符串。"""
    return (
        SystemPromptBuilder()
        .add_tool_system(tools)
        .add_skill_system(skills or [])
        .add_memory_system()
        .add_knowledge_system()
        .add_workspace()
        .add_user_identity()
        .add_project_context()
        .add_runtime_info()
        .build()
    )
