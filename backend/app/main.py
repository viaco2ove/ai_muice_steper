"""main.py - FastAPI 入口 + WebSocket 对话 + 静态托管前端"""
import json
import asyncio
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import config
from .api.router import router as api_router
from .core.agent_core import AgentCore
from .core.project_manager import ProjectManager
from .core.llm_agent import LLMAgent

app = FastAPI(title="AI音乐工程工作台", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

# 单例
_pm = ProjectManager()
_core = AgentCore()
_agent = LLMAgent(_core, _pm)


@app.get("/")
def root():
    return {"name": "AI音乐工程工作台", "status": "running",
            "skills": len(_core.list_skills())}


@app.get("/api/health")
def health():
    return {"ok": True, "skills": len(_core.list_skills()),
            "projects": len(_pm.list_projects())}


@app.websocket("/ws/chat")
async def ws_chat(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                await ws.send_json({"type": "error", "msg": "非JSON消息"})
                continue
            if msg.get("type") == "ping":
                await ws.send_json({"type": "pong"})
                continue
            if msg.get("type") != "chat":
                continue
            user_msg = msg.get("msg", "")
            project = msg.get("project")
            audio_path = msg.get("audio_path")
            history = msg.get("history", [])

            async def ws_send(obj):
                await ws.send_json(obj)

            await ws.send_json({"type": "text", "msg": f"🧑 {user_msg}",
                                "stream": False, "role": "user_echo"})
            # 在线程池跑 agent（含 subprocess）
            await _agent.handle(user_msg, project, history, audio_path, ws_send)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_json({"type": "error", "msg": f"服务异常: {e}"})
        except Exception:
            pass


# 静态托管前端 dist（构建后）
_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="frontend")