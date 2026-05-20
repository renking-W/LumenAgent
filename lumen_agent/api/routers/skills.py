"""SKILL 列表路由：GET /v1/skills。"""

from __future__ import annotations

from fastapi import APIRouter

from lumen_agent.agent.skills import load_skills
from lumen_agent.api.schemas.capability_dtos import SkillInfo

router = APIRouter(prefix="/v1", tags=["capabilities"])


@router.get("/skills", response_model=list[SkillInfo])
async def list_skills() -> list[SkillInfo]:
    """返回当前扫描到的所有 SKILL（含不可用项），含可用性与缺失 env 信息。"""
    return [
        SkillInfo(
            name=s.name,
            description=s.description,
            path=str(s.path),
            available=s.available,
            requires_env=list(s.requires.env),
            primary_env=s.primary_env,
            missing_envs=list(s.missing_envs),
            emoji=s.emoji,
        )
        for s in load_skills()
    ]
