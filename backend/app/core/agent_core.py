"""agent_core.py - 简化版 WorkBuddy：扫描/校验/执行 .workbuddy 技能

零 AI 逻辑，只接收结构化参数，subprocess 调技能脚本，捕获日志，返回产物。
"""
import os
import re
import sys
import json
import subprocess
from pathlib import Path
from typing import Callable, Optional

from ..config import config


def _parse_frontmatter(text: str) -> dict:
    """解析 SKILL.md 的 YAML frontmatter（用 yaml 库，正确处理引号/多行）"""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return {}
    import yaml
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except Exception:
        # 降级：逐行裸解析
        meta = {}
        for line in m.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                meta[k.strip()] = v.strip()
    # params 字段若是 str 转 dict
    if "params" in meta and isinstance(meta["params"], str):
        try:
            import json
            meta["params"] = json.loads(meta["params"])
        except Exception:
            pass
    if "executable" in meta:
        meta["executable"] = bool(meta["executable"])
    else:
        meta["executable"] = False
    return meta


class AgentCore:
    def __init__(self, workbuddy_dir: Path = None, workspace_dir: Path = None):
        self.wb_dir = Path(workbuddy_dir or config.workbuddy_dir)
        self.ws_dir = Path(workspace_dir or config.workspace_dir)
        self.skills_dir = self.wb_dir / "skills"
        self.skills: dict = {}
        self.scan()

    # ---------------------------------------------------------------- 扫描
    def scan(self) -> dict:
        """启动时遍历 .workbuddy/skills/*/SKILL.md，读 frontmatter"""
        self.skills = {}
        if not self.skills_dir.exists():
            return self.skills
        for sd in sorted(self.skills_dir.iterdir()):
            if not sd.is_dir():
                continue
            sm = sd / "SKILL.md"
            if not sm.exists():
                continue
            try:
                text = sm.read_text(encoding="utf-8")
            except Exception:
                continue
            meta = _parse_frontmatter(text)
            name = meta.get("name", sd.name)
            scripts_dir = sd / "scripts"
            scripts = [s.name for s in scripts_dir.glob("*.py")] if scripts_dir.exists() else []
            self.skills[name] = {
                "name": name,
                "description": meta.get("description", "").strip('"').strip("'"),
                "triggers": meta.get("触发词", ""),
                "entry_script": meta.get("entry_script", "").strip('"').strip("'"),
                "params": meta.get("params", {}) if isinstance(meta.get("params"), dict) else {},
                "executable": meta.get("executable", False),
                "dir": str(sd),
                "scripts": scripts,
            }
        return self.skills

    def list_skills(self) -> list:
        return list(self.skills.values())

    def get_skill(self, name: str) -> Optional[dict]:
        return self.skills.get(name)

    # ---------------------------------------------------------------- 执行
    def run_skill(self, tool: str, args: dict,
                  on_log: Callable[[str], None] = None,
                  timeout: int = 1800) -> dict:
        """执行单技能。返回 {status, files, logs, error}"""
        result = {"status": "running", "files": [], "logs": [], "error": None, "tool": tool}
        if tool not in self.skills:
            result["status"] = "error"
            result["error"] = f"未知技能: {tool}"
            return result
        skill = self.skills[tool]
        if not skill.get("executable"):
            result["status"] = "error"
            result["error"] = f"技能 {tool} 为纯提示词技能(executable=false)，需 LLM 按 SKILL.md 执行，不能直接 subprocess 调用"
            return result

        entry = skill.get("entry_script")
        if not entry:
            # 兜底：取 scripts 第一个 .py
            if skill.get("scripts"):
                entry = "scripts/" + skill["scripts"][0]
            else:
                result["status"] = "error"
                result["error"] = f"技能 {tool} 无 entry_script 且无 scripts"
                return result

        script_path = Path(skill["dir"]) / entry
        if not script_path.exists():
            result["status"] = "error"
            result["error"] = f"入口脚本不存在: {script_path}"
            return result

        cmd = [config.python_exe, str(script_path)] + self._build_args(args, skill.get("params", {}))
        result["logs"].append("$ " + " ".join(cmd))

        # 记录执行前 workspace 工程目录文件快照（用于收集新增产物）
        project_name = args.get("project") or args.get("--project") or args.get("title") or args.get("--title")
        snap_before = self._snapshot_project(project_name) if project_name else set()

        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                cwd=str(self.wb_dir.parent), text=True,
                encoding="utf-8", errors="replace", bufsize=1,
            )
            try:
                for line in iter(proc.stdout.readline, ""):
                    line = line.rstrip()
                    if line:
                        result["logs"].append(line)
                        if on_log:
                            try: on_log(line)
                            except Exception: pass
            except Exception as e:
                result["logs"].append(f"[read-err] {e}")
            proc.wait(timeout=timeout)
            rc = proc.returncode
        except subprocess.TimeoutExpired:
            proc.kill()
            result["status"] = "error"
            result["error"] = f"技能 {tool} 执行超时({timeout}s)"
            return result
        except FileNotFoundError as e:
            result["status"] = "error"
            result["error"] = f"执行失败(解释器或脚本找不到): {e}"
            return result

        if rc != 0:
            result["status"] = "error"
            result["error"] = f"技能 {tool} 退出码 {rc}"
        else:
            result["status"] = "ok"

        # 收集产物
        result["files"] = self._collect_outputs(project_name, snap_before)
        return result

    # ---------------------------------------------------------------- 辅助
    def _build_args(self, args: dict, params_spec: dict) -> list:
        """dict 参数 -> CLI flags。
        args 的 key 可能是 'project' 或 '--project'，统一处理。
        布尔 True -> 仅加 flag；False/None -> 跳过。
        """
        out = []
        for k, v in args.items():
            if v is None or v is False:
                continue
            flag = k if k.startswith("-") else ("--" + k)
            if v is True:
                out.append(flag)
            else:
                out.append(flag)
                out.append(str(v))
        return out

    def _snapshot_project(self, project_name: str) -> set:
        pdir = config.project_dir / project_name
        if not pdir.exists():
            return set()
        return {str(f) for f in pdir.rglob("*") if f.is_file()}

    def _collect_outputs(self, project_name: str, snap_before: set) -> list:
        if not project_name:
            return []
        pdir = config.project_dir / project_name
        if not pdir.exists():
            return []
        after = {str(f) for f in pdir.rglob("*") if f.is_file()}
        new = sorted(after - snap_before)
        # 转相对路径
        return [str(Path(f).relative_to(config.project_dir)) for f in new]
