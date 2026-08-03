"""config.py - 后端配置，读 .env"""
import os
import json
from pathlib import Path
from dotenv import load_dotenv

# 项目根 = backend 的上一级
ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def _load_models_json():
    """读 models.json: {models:[...], skill_ai:{model:id}, <skill>:{model:id}}"""
    p = ROOT / "models.json"
    if not p.exists():
        return {"models": [], "skill_ai": {}}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"models": [], "skill_ai": {}}


class Config:
    # 路径
    root_dir = ROOT
    workbuddy_dir = ROOT / ".workbuddy"
    workspace_dir = ROOT / "workspace"
    project_dir = workspace_dir / "project"

    # 服务
    host = os.getenv("BACKEND_HOST", "127.0.0.1")
    port = int(os.getenv("BACKEND_PORT", "8000"))

    # Python 解释器（复用 .venv，确保技能脚本用相同环境）
    python_exe = os.getenv("PYTHON_EXE", str(ROOT / ".venv" / "python.exe"))

    # LLM (OpenAI 兼容协议) - 全局默认，可被 models.json 的 skill 级配置覆盖
    llm_base_url = os.getenv("LLM_BASE_URL", "http://127.0.0.1:3428/v1")
    llm_api_key = os.getenv("LLM_API_KEY", "orcg")
    llm_model = os.getenv("LLM_MODEL", "orcg")

    # models.json: 技能级 LLM 配置
    models_json_path = ROOT / "models.json"
    models_config = _load_models_json()

    # CORS
    cors_origins = ["http://127.0.0.1:5173", "http://localhost:5173",
                    "http://127.0.0.1:8000", "http://localhost:8000"]


config = Config()
