"""schemas.py - Pydantic 请求/响应模型"""
from pydantic import BaseModel
from typing import Optional


class NewProjectReq(BaseModel):
    name: str
    style: Optional[str] = ""
    bpm: Optional[int] = 0
    key: Optional[str] = ""


class SaveTrackReq(BaseModel):
    md: str


class RunSkillReq(BaseModel):
    args: dict = {}


class ChatMessage(BaseModel):
    msg: str
    project: Optional[str] = None
    audio_path: Optional[str] = None
    history: list = []