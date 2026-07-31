"""audio 路由：上传音频"""
import shutil
from fastapi import APIRouter, UploadFile, File, Form
from pathlib import Path
from ..config import config

router = APIRouter(tags=["audio"])


@router.post("/audio/upload")
async def upload_audio(file: UploadFile = File(...), project: str = Form(None)):
    # 存到 workspace/project/{project}/ 或 temp
    if project:
        dest_dir = config.project_dir / project
        dest_dir.mkdir(parents=True, exist_ok=True)
    else:
        dest_dir = config.workspace_dir / "uploads"
        dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / file.filename
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"audio_path": str(dest), "filename": file.filename}