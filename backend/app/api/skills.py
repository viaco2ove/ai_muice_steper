"""skills 路由：列出可用技能"""
from fastapi import APIRouter
from ..core.agent_core import AgentCore

router = APIRouter(tags=["skills"])


@router.get("/skills")
def list_skills():
    core = AgentCore()
    return core.list_skills()