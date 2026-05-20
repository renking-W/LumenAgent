"""SKILL 元数据结构定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class SkillRequires:
    """SKILL 的依赖声明（仅 env 参与本期可用性校验）。"""

    env: tuple[str, ...] = ()
    bins: tuple[str, ...] = ()
    any_bins: tuple[str, ...] = ()
    config: tuple[str, ...] = ()


@dataclass(frozen=True)
class SkillMeta:
    """单个 SKILL 的元信息，由 loader 解析 SKILL.md frontmatter 后生成。"""

    name: str
    description: str
    path: Path                        # SKILL.md 绝对路径，挂载到 system prompt
    available: bool                   # requires.env + primaryEnv 全部满足则 True
    missing_envs: tuple[str, ...]     # 缺失的环境变量名列表
    primary_env: str | None = None
    requires: SkillRequires = field(default_factory=SkillRequires)
    emoji: str = ""
    raw_frontmatter: dict = field(default_factory=dict)  # 保留全部字段供扩展
