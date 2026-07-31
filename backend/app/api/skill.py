"""skill 路由：手动单技能执行"""
from fastapi import APIRouter, HTTPException
from ..schemas.schemas import RunSkillReq
from ..core.agent_core import AgentCore

router = APIRouter(tags=["skill"])


@router.post("/skill/{tool}")
def run_skill(tool: str, req: RunSkillReq):
    core = AgentCore()
    if not core.get_skill(tool):
        raise HTTPException(404, f"未知技能: {tool}")
    result = core.run_skill(tool, req.args)
    return result