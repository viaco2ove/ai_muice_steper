"""api 路由聚合"""
from fastapi import APIRouter
from . import project, skill, audio, export, skills

router = APIRouter(prefix="/api")
router.include_router(skills.router)
router.include_router(project.router)
router.include_router(skill.router)
router.include_router(audio.router)
router.include_router(export.router)