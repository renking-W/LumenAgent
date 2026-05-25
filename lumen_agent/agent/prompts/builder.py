"""系统提示词构造器：按固定顺序组装各子系统的 system 提示词。

构造顺序：
  1. 工具系统（已实现）
  2. 技能系统（已实现）
  3. 记忆系统（预留）
  4. 知识系统（预留）
  5. 工作空间（预留）
  6. 用户身份（预留）
  7. 项目上下文（预留）
  8. 运行时信息（预留）
"""

from __future__ import annotations

import json
from pathlib import Path

from lumen_agent.agent.skills.meta import SkillMeta
from lumen_agent.agent.tools.base import BaseTool
from lumen_agent.infrastructure.sqlite_knowledge import SqliteKnowledgeRepository

_SECTION_SEP = "\n\n---\n\n"


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
        import asyncio

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
            lines.append(
                f"- `{param_name}`（{param_type}，{required_label}）：{param_desc}"
            )

    return "\n".join(lines)


class SystemPromptBuilder:
    """链式系统提示词构造器。

    调用各 add_*() 方法填充子系统内容，最终调用 build() 返回完整 system 字符串。
    尚未实现的子系统方法以空实现预留，签名保持稳定以便后续补充。
    """

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
        section = (
            "# 工具系统\n\n"
            "你可以调用以下工具：\n\n"
            + _SECTION_SEP
            + tool_blocks
        )
        self._sections.append(section)
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
            "> **重要约束**：调用任何技能前，**必须先使用 `read` 工具读取该技能的 SKILL.md 完整内容**，"
            "再按其中说明执行操作。本节只提供技能的名称、描述与文件路径，不会自动传入任何参数。"
            "如果没有技能明确适用：不要读取任何 SKILL.md，直接使用通用工具。",
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
        """记忆系统（预留）。"""
        return self

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
                file_name = item.get("file_name") or "未知文件"
                source = item.get("source") or "未知来源"
                lines.append(f"- `{file_name}`（来源：`{source}`）")
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
                file_name = doc.get("file_name") or "未知文件"
                source_name = doc.get("source_name") or "未知来源"
                status = doc.get("status") or "unknown"
                chunk_count = doc.get("chunk_count")
                updated_at = doc.get("updated_at") or "未知时间"
                lines.append(
                    f"- `{file_name}`（来源：`{source_name}`，状态：`{status}`，chunks：{chunk_count}，更新于：`{updated_at}`）"
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

    def add_workspace(self) -> "SystemPromptBuilder":
        """工作空间：直接读取 RULE.md 并拼接到上下文中。"""
        rule_path = Path(__file__).resolve().parent / "docs" / "RULE.md"
        if not rule_path.exists():
            return self

        rule_text = rule_path.read_text(encoding="utf-8").strip()
        if not rule_text:
            return self

        self._sections.append("\n\n" + rule_text + "\n\n")
        return self

    def add_user_identity(self) -> "SystemPromptBuilder":
        """用户身份：直接读取 USER.md 并拼接到上下文中。"""
        user_path = Path(__file__).resolve().parent / "docs" / "USER.md"
        if not user_path.exists():
            return self

        user_text = user_path.read_text(encoding="utf-8").strip()
        if not user_text:
            return self

        self._sections.append("\n\n" + user_text + "\n\n")
        return self

    def add_project_context(self) -> "SystemPromptBuilder":
        """项目上下文：依次读取 ME.md 与 MEMORY.md 并拼接到上下文中。"""
        me_path = Path(__file__).resolve().parent / "docs" / "ME.md"
        memory_path = Path(__file__).resolve().parent / "docs" / "MEMORY.md"

        sections: list[str] = []
        for title, path in (("自我信息", me_path), ("记忆信息", memory_path)):
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8").strip()
            if not text:
                continue
            sections.append(f"\n\n{text}")

        if sections:
            self._sections.append("\n\n---\n\n".join(sections))
        return self

    def add_runtime_info(self   ) -> "SystemPromptBuilder":
        """运行时信息：读取当前系统时间并拼接到上下文中。"""
        from datetime import datetime

        now_text = datetime.now().astimezone().isoformat(timespec="seconds")
        self._sections.append(f"## 系统时钟\n\n当前系统时间：`{now_text}`")
        return self

    # ------------------------------------------------------------------ #
    # 最终构建                                                              #
    # ------------------------------------------------------------------ #

    def build(self) -> str:
        """将所有已填充的节拼接为最终 system 字符串。"""
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
