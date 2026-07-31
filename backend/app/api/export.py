"""export 路由：导出文件"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from ..config import config

router = APIRouter(tags=["export"])


@router.get("/export/{name}/{ftype}")
def export_file(name: str, ftype: str):
    """导出工程内最新文件。ftype: mid/wav/mscx/lyrics/mp3"""
    pdir = config.project_dir / name
    if not pdir.exists():
        raise HTTPException(404, f"工程不存在: {name}")
    ext_map = {"mid": ".mid", "wav": ".wav", "mscx": ".mscx",
               "lyrics": ".txt", "mp3": ".mp3"}
    ext = ext_map.get(ftype)
    if not ext:
        raise HTTPException(400, f"不支持的类型: {ftype}")
    # 找最新的该类型文件
    files = sorted(pdir.rglob(f"*{ext}"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not files:
        raise HTTPException(404, f"工程内无 {ftype} 文件")
    f = files[0]
    return FileResponse(str(f), filename=f.name)