"""能力列表接口 DTO：工具与 SKILL 的对外展示结构。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ToolInfo(BaseModel):
    """单个工具的对外展示信息。"""

    name: str
    description: str
    parameters: dict = Field(default_factory=dict)


class SkillInfo(BaseModel):
    """单个 SKILL 的对外展示信息。"""

    name: str
    description: str
    path: str
    available: bool
    requires_env: list[str] = Field(default_factory=list)
    primary_env: str | None = None
    missing_envs: list[str] = Field(default_factory=list)
    emoji: str = ""
