"""project 路由：工程 CRUD + 单轨读写"""
from fastapi import APIRouter, HTTPException
from ..schemas.schemas import NewProjectReq, SaveTrackReq
from ..core.project_manager import ProjectManager

router = APIRouter(tags=["project"])
pm = ProjectManager()


@router.get("/projects")
def list_projects():
    return pm.list_projects()


@router.post("/project/new")
def new_project(req: NewProjectReq):
    return pm.init_project(req.name, req.style, req.bpm, req.key)


@router.get("/project/{name}")
def get_project(name: str):
    try:
        return pm.get_project(name)
    except FileNotFoundError:
        raise HTTPException(404, f"工程不存在: {name}")


@router.get("/project/{name}/track/{tid}")
def get_track(name: str, tid: str):
    return pm.get_track(name, tid)


@router.put("/project/{name}/track/{tid}")
def save_track(name: str, tid: str, req: SaveTrackReq):
    return pm.save_track(name, tid, req.md)


@router.get("/project/{name}/files")
def list_files(name: str):
    return pm.list_files(name)