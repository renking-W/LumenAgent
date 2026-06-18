"""SKILL 加载器：扫描 work_space/skills/ 目录，解析 frontmatter，校验 env，提供 mtime 缓存。"""

from __future__ import annotations

import logging
import os
from typing import Any

import yaml

from lumen_agent.agent.skills.meta import SkillMeta, SkillRequires
from lumen_agent.application.uitls.dir_guide import DirGuide

logger = logging.getLogger(__name__)

SKILLS_DIR = DirGuide.skills_dir()

# 缓存：(max_mtime, file_count, list[SkillMeta])
# 任一 SKILL.md 的修改时间或文件数量变化都会触发重新加载
_CACHE: tuple[float, int, list[SkillMeta]] | None = None


def load_skills() -> list[SkillMeta]:
    """扫描 work_space/skills/ 下所有一级子目录的 SKILL.md，返回解析后的元数据列表。

    结果按 mtime 签名缓存；任一文件改动自动失效。
    """
    global _CACHE  # noqa: PLW0603

    files = sorted(SKILLS_DIR.glob("*/SKILL.md"))
    if not files:
        return []

    max_mtime = max(f.stat().st_mtime for f in files)
    count = len(files)
    sig = (max_mtime, count)

    if _CACHE is not None and _CACHE[:2] == sig:
        return _CACHE[2]

    env_view = _build_env_view()
    skills: list[SkillMeta] = []
    for f in files:
        meta = _parse_one(f, env_view)
        if meta is not None:
            skills.append(meta)

    _CACHE = (*sig, skills)  # type: ignore[assignment]
    logger.debug("Skills reloaded: %d skills found", len(skills))
    return skills


def clear_skill_cache() -> None:
    """清除缓存，下次调用 load_skills() 时强制重新扫描。"""
    global _CACHE  # noqa: PLW0603
    _CACHE = None


# ---------------------------------------------------------------------------
# 内部实现
# ---------------------------------------------------------------------------

def _build_env_view() -> dict[str, str]:
    """合并 .env 文件与系统环境变量，返回所有非空 key 的映射。

    优先级：os.environ > .env 文件（与 pydantic-settings 保持一致）。
    """
    env_file = DirGuide.env_path()
    merged: dict[str, str] = {}

    if env_file.exists():
        try:
            from dotenv import dotenv_values  # pydantic-settings 已带 python-dotenv
            parsed = dotenv_values(env_file) or {}
            merged.update({k: v for k, v in parsed.items() if v})
        except Exception:  # noqa: BLE001
            pass

    merged.update({k: v for k, v in os.environ.items() if v})
    return merged


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """从 Markdown 文本中提取 YAML frontmatter。

    返回 (frontmatter_dict, body_text)；若无合法 frontmatter 则返回 ({}, text)。
    """
    text = text.lstrip()
    if not text.startswith("---"):
        return {}, text

    # 找第二个 '---' 分隔符
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text

    yaml_block = text[3:end].strip()
    body = text[end + 4:].lstrip("\n")

    try:
        data = yaml.safe_load(yaml_block)
    except yaml.YAMLError as exc:
        logger.warning("Failed to parse YAML frontmatter: %s", exc)
        return {}, text

    if not isinstance(data, dict):
        return {}, text

    return data, body


def _parse_requires(raw: Any) -> SkillRequires:
    """将 frontmatter 中的 requires 字段解析为 SkillRequires。"""
    if not isinstance(raw, dict):
        return SkillRequires()

    def _to_tuple(val: Any) -> tuple[str, ...]:
        if isinstance(val, list):
            return tuple(str(x) for x in val if x)
        if isinstance(val, str):
            return (val,)
        return ()

    return SkillRequires(
        env=_to_tuple(raw.get("env")),
        bins=_to_tuple(raw.get("bins")),
        any_bins=_to_tuple(raw.get("anyBins")),
        config=_to_tuple(raw.get("config")),
    )


def _check_availability(
    requires: SkillRequires,
    primary_env: str | None,
    env_view: dict[str, str],
) -> tuple[bool, tuple[str, ...]]:
    """校验 env 依赖，返回 (available, missing_envs)。"""
    needed: list[str] = list(requires.env)
    if primary_env:
        needed.append(primary_env)

    missing = tuple(k for k in needed if k not in env_view)
    return (len(missing) == 0), missing


def _resolve_meta_block(frontmatter: dict[str, Any]) -> dict[str, Any]:
    """从 frontmatter 中提取包含 requires/primaryEnv/emoji 的元数据块。

    支持两种格式：
    - 嵌套格式：metadata 下可有多个子块（如 openclaw、clawdbot），
      将所有子块浅合并后返回，后出现的子块字段覆盖前者。
    - 扁平格式：顶层直接包含 {requires, primaryEnv, emoji}。

    优先尝试嵌套格式，metadata 不存在或无子块时回退到顶层。
    """
    metadata = frontmatter.get("metadata")
    if isinstance(metadata, dict):
        merged: dict[str, Any] = {}
        for block in metadata.values():
            if isinstance(block, dict):
                merged.update(block)
        if merged:
            return merged
    return frontmatter


def _parse_one(skill_md: Path, env_view: dict[str, str]) -> SkillMeta | None:
    """解析单个 SKILL.md，返回 SkillMeta；格式有误则记日志并返回 None。"""
    try:
        text = skill_md.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Cannot read %s: %s", skill_md, exc)
        return None

    frontmatter, _ = _parse_frontmatter(text)
    if not frontmatter:
        logger.warning("No valid frontmatter in %s, skipping", skill_md)
        return None

    name = str(frontmatter.get("name", "")).strip()
    description = str(frontmatter.get("description", "")).strip()
    if not name or not description:
        logger.warning("Missing required 'name' or 'description' in %s, skipping", skill_md)
        return None

    # 兼容嵌套格式（metadata.openclaw.*）与扁平格式（顶层字段）
    meta_block = _resolve_meta_block(frontmatter)

    primary_env = meta_block.get("primaryEnv") or meta_block.get("primary_env")
    if primary_env:
        primary_env = str(primary_env).strip() or None

    requires = _parse_requires(meta_block.get("requires"))
    available, missing_envs = _check_availability(requires, primary_env, env_view)

    emoji = str(meta_block.get("emoji", "")).strip()

    return SkillMeta(
        name=name,
        description=description,
        path=skill_md.resolve(),
        available=available,
        missing_envs=missing_envs,
        primary_env=primary_env,
        requires=requires,
        emoji=emoji,
        raw_frontmatter=frontmatter,
    )
