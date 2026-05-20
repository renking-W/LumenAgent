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

from lumen_agent.agent.skills.meta import SkillMeta
from lumen_agent.agent.tools.base import BaseTool

_SECTION_SEP = "\n\n---\n\n"


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
            "## 工具系统\n\n"
            "你可以调用以下工具：\n\n"
            + _SECTION_SEP
            + tool_blocks
        )
        self._sections.append(section)
        return self

    # ------------------------------------------------------------------ #
    # 2‑8. 预留子系统（签名稳定，暂不填充内容）                            #
    # ------------------------------------------------------------------ #

    def add_skill_system(self, skills: list[SkillMeta]) -> "SystemPromptBuilder":
        """将技能列表渲染为技能系统说明并追加到提示词。"""
        if not skills:
            return self

        available = [s for s in skills if s.available]
        unavailable = [s for s in skills if not s.available]

        lines: list[str] = [
            "## 技能系统",
            "",
            "以下是可供调用的技能列表（仅展示元信息）。",
            "",
            "> **重要约束**：调用任何技能前，**必须先使用 `read` 工具读取该技能的 SKILL.md 完整内容**，"
            "再按其中说明执行操作。本节只提供技能的名称、描述与文件路径，不会自动传入任何参数。"
            "如果没有技能明确适用：不要读取任何 SKILL.md，直接使用通用工具。",
        ]

        if available:
            lines += ["", "### 可使用的技能", ""]
            for s in available:
                prefix = f"{s.emoji} " if s.emoji else ""
                lines.append(f"- {prefix}**{s.name}** — {s.description}")
                lines.append(f"  path: `{s.path}`")

        if unavailable:
            lines += ["", "### 不可使用的技能（环境变量未配置）", ""]
            for s in unavailable:
                prefix = f"{s.emoji} " if s.emoji else ""
                missing = ", ".join(s.missing_envs)
                lines.append(f"- {prefix}**{s.name}** — {s.description}")
                lines.append(f"  path: `{s.path}`")
                lines.append(f"  缺失环境变量: `{missing}`")

        self._sections.append("\n".join(lines))
        return self

    def add_memory_system(self) -> "SystemPromptBuilder":
        """记忆系统（预留）。"""
        return self

    def add_knowledge_system(self) -> "SystemPromptBuilder":
        """知识系统（预留）。"""
        return self

    def add_workspace(self) -> "SystemPromptBuilder":
        """工作空间（预留）。"""
        return self

    def add_user_identity(self) -> "SystemPromptBuilder":
        """用户身份（预留）。"""
        return self

    def add_project_context(self) -> "SystemPromptBuilder":
        """项目上下文（预留）。"""
        return self

    def add_runtime_info(self) -> "SystemPromptBuilder":
        """运行时信息（预留）。"""
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
