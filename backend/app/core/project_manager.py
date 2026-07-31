"""project_manager.py - 工程目录/MD/json 读写 + 双向同步 + LLM 上下文摘要"""
import json
from pathlib import Path
from typing import Optional

from ..config import config
from .md_parser import parse_track_md, serialize_track_md, parse_project_md


class ProjectManager:
    def __init__(self):
        self.pdir = config.project_dir  # workspace/project

    # ---------------------------------------------------------------- 列表
    def list_projects(self) -> list:
        if not self.pdir.exists():
            return []
        out = []
        for d in sorted(self.pdir.iterdir()):
            if not d.is_dir():
                continue
            se = d / "song_engineer" / "song_engineer.json"
            tracks = list((d / "song_engineer" / "track").glob("*.json")) if (d / "song_engineer" / "track").exists() else []
            out.append({
                "name": d.name,
                "has_engineer": se.exists(),
                "tracks_count": len(tracks),
                "updated": se.stat().st_mtime if se.exists() else d.stat().st_mtime,
            })
        return out

    # ---------------------------------------------------------------- 读取
    def get_project(self, name: str) -> dict:
        """读 song_engineer.json，没有则从 project.md + track/* 临时聚合"""
        se_json = self.pdir / name / "song_engineer" / "song_engineer.json"
        if se_json.exists():
            return json.loads(se_json.read_text(encoding="utf-8"))
        # 兜底：从 project.md 聚合
        return self._aggregate_from_md(name)

    def _aggregate_from_md(self, name: str) -> dict:
        pdir = self.pdir / name
        data = {"meta": {"song_name": name}, "basic": {}, "sections": [],
                "chord_progression": {}, "tracks": [], "diagnosis": {}}
        pm = pdir / "project.md"
        if pm.exists():
            parsed = parse_project_md(pm.read_text(encoding="utf-8"))
            data["basic"] = parsed.get("basic", {})
            data["sections"] = parsed.get("sections_table", [])
        # 分轨
        track_dir = pdir / "song_engineer" / "track"
        if track_dir.exists():
            for jf in sorted(track_dir.glob("*.json")):
                try:
                    tj = json.loads(jf.read_text(encoding="utf-8"))
                    data["tracks"].append({
                        "id": str(tj.get("track_id", jf.stem)),
                        "name": tj.get("name", jf.stem),
                        "role": tj.get("role", ""),
                        "status": tj.get("status", ""),
                        "instrument": tj.get("instrument", ""),
                    })
                except Exception:
                    pass
        return data

    # ---------------------------------------------------------------- 单轨
    def get_track(self, name: str, tid: str) -> dict:
        """返回 {md, json}"""
        track_dir = self.pdir / name / "song_engineer" / "track"
        # tid 可能是 "01" 或 "01_吉他"
        md_path = self._find_track_file(track_dir, tid, ".md")
        jf_path = self._find_track_file(track_dir, tid, ".json")
        md = md_path.read_text(encoding="utf-8") if md_path and md_path.exists() else ""
        js = json.loads(jf_path.read_text(encoding="utf-8")) if jf_path and jf_path.exists() else {}
        return {"md": md, "json": js}

    def save_track(self, name: str, tid: str, md: str) -> dict:
        """写回 md，并从 md 重新解析更新 json（双向同步）"""
        track_dir = self.pdir / name / "song_engineer" / "track"
        track_dir.mkdir(parents=True, exist_ok=True)
        md_path = self._find_track_file(track_dir, tid, ".md")
        if not md_path:
            md_path = track_dir / f"{tid}.md"
        md_path.write_text(md, encoding="utf-8")
        # 解析 md 更新 json（保留原 json 字段，合并 info）
        jf_path = md_path.with_suffix(".json")
        existing = {}
        if jf_path.exists():
            try: existing = json.loads(jf_path.read_text(encoding="utf-8"))
            except Exception: existing = {}
        parsed = parse_track_md(md)
        existing["info"] = parsed.get("info", {})
        existing["name"] = existing.get("name", md_path.stem)
        jf_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
        return existing

    def _find_track_file(self, track_dir: Path, tid: str, ext: str) -> Optional[Path]:
        if not track_dir.exists():
            return None
        # 精确名
        c = track_dir / f"{tid}{ext}"
        if c.exists():
            return c
        # 前缀匹配 (01 -> 01_吉他)
        for f in track_dir.glob(f"*{ext}"):
            stem = f.stem
            if stem == tid or stem.startswith(tid + "_") or stem.startswith(tid):
                return f
        return None

    # ---------------------------------------------------------------- 工程
    def init_project(self, name: str, style: str = "", bpm: int = 0, key: str = "") -> dict:
        pdir = self.pdir / name
        pdir.mkdir(parents=True, exist_ok=True)
        (pdir / "song_engineer" / "track").mkdir(parents=True, exist_ok=True)
        pm = pdir / "project.md"
        if not pm.exists():
            skeleton = f"""# 歌曲工程：{name}

## 基础信息
| 字段 | 值 |
|------|-----|
| 调性 | {key} |
| BPM | {bpm} |
| 风格 | {style} |
| 情绪 | |
| 创作日期 | |

## 段落结构总览
| 段落 | 小节 | 和弦进行 | 备注 |
|------|------|----------|------|
| 前奏 | 1-4 | | |
| 主歌A | 5-12 | | |
| 副歌 | 13-20 | | |

## 分轨规划
（待规划）

## 创作笔记
（新建工程）
"""
            pm.write_text(skeleton, encoding="utf-8")
        return {"name": name, "path": str(pdir)}

    # ---------------------------------------------------------------- 摘要(LLM上下文)
    def summary(self, name: str) -> str:
        """给 LLM 的精简上下文文本"""
        d = self.get_project(name)
        lines = [f"【当前歌曲工程摘要】", f"歌名: {name}"]
        b = d.get("basic", {})
        if b:
            lines.append(f"调性: {b.get('调性', b.get('key','?'))} | BPM: {b.get('BPM', b.get('bpm','?'))} | 风格: {b.get('风格', b.get('style','?'))}")
        secs = d.get("sections", [])
        if secs:
            lines.append("段落: " + " ".join(f"{s.get('section',s.get('段落',''))}({s.get('bars',s.get('小节',''))})" for s in secs))
        cp = d.get("chord_progression", {}).get("by_section", {})
        if cp:
            for sec, chords in list(cp.items())[:4]:
                lines.append(f"  {sec}: {'-'.join(chords)}")
        trs = d.get("tracks", [])
        if trs:
            lines.append("轨道状态:")
            for t in trs:
                lines.append(f"  {t.get('name','')} {t.get('status','')} ({t.get('instrument','')})")
        dg = d.get("diagnosis", {})
        if dg:
            comp = dg.get("completeness", {})
            lines.append(f"诊断: 完整性{comp.get('score','?')} | 待优化: {', '.join(dg.get('optimization_space', [])[:3])}")
        return "\n".join(lines)

    # ---------------------------------------------------------------- 文件列表
    def list_files(self, name: str) -> list:
        pdir = self.pdir / name
        if not pdir.exists():
            return []
        out = []
        for f in pdir.rglob("*"):
            if f.is_file():
                ext = f.suffix.lower().lstrip(".")
                t = {"mid": "mid", "wav": "wav", "mp3": "mp3", "mscx": "mscx",
                     "txt": "txt", "json": "json", "md": "md"}.get(ext, "other")
                out.append({
                    "path": str(f.relative_to(self.pdir)),
                    "type": t, "size": f.stat().st_size, "time": f.stat().st_mtime,
                })
        return sorted(out, key=lambda x: x["time"], reverse=True)