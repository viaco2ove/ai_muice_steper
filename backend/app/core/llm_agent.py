"""llm_agent.py - LLM 意图解析 + 任务链编排 + 串行调度 + 二次总结

LLM 返回两类：
1. 技能任务JSON {need_tool:true, task_chain:[{tool,args}]} -> Agent Core 串行执行
2. 纯文字 -> 直接流式回前端
"""
import json
import re
from typing import Optional

from .agent_core import AgentCore
from .llm_client import get_llm
from .project_manager import ProjectManager

SYSTEM_PROMPT = """你是音乐创作调度助手，可调用本地音乐技能完成歌曲制作。

## 可用技能清单与入参规范
audio_chord_recognizer: {input(音频文件绝对路径,required)}  哼唱->BPM/调性/和弦/旋律MIDI
ai_chords_master: {--title(歌曲名), --progression(基础和弦逗号分隔,required)}  生成完整段落和弦进行
openutau_lyrics: {--project(歌曲名,required), --midi(MIDI文件名,required)}  输出OpenUTAU逐音符歌词txt
musescore-cooperate: {--project(歌曲名,required), --tracks(逗号分隔的轨道ID,如"01_吉他,02_主唱"), --full(布尔true生成总谱), --bpm(BPM数字)}  生成mscx乐谱(含音色配置)
remix-master: {--project(歌曲名)}  多轨混音
wav_mid_human: {input(输入WAV绝对路径,required), -o(输出目录)}  人声WAV转MIDI(清洗碎音)
song_engineer: {input(输入JSON绝对路径,required), -o(输出MIDI路径)}  分轨MIDI导出(注:工程聚合诊断需LLM按SKILL.md执行)

## 参数重要约定
- --tracks 的值必须是轨道ID(如"01_吉他"),不是乐器中文名(不是"木吉他")。轨道ID来自工程摘要的"轨道状态"列表。
- --full 生成总谱时传 true(布尔),不要传字符串。
- 生成全部轨道总谱时,用 musescore-cooperate 带 --full=true,不需要指定 --tracks。

## 纯提示词技能(也可放入 task_chain，后端用对应模型按SKILL.md执行)
melody_master: {project}  旋律设计与优化
muse-lyrics-gen: {project}  生成歌词
muse_ai_master: {project}  Muse AI歌词结构+生成
minimax_music_v3: {project}  MiniMax歌词格式转换
这些技能无脚本，放入 task_chain 时只需给 {project} 参数，后端会调用各自配置的模型执行。

## 输出规则（严格遵守）
- 需要执行技能：仅输出纯净JSON，禁止任何解释文字、禁止markdown代码块
{"need_tool": true, "task_chain": [{"tool": "技能名称", "args": {"参数键": "值"}}]}
- 无需执行技能（乐理答疑/旋律点评/创作建议）：直接输出自然中文，不输出JSON

## 执行逻辑
1. 音频分析类技能(audio_chord_recognizer/wav_mid_human)优先执行
2. 生成类任务串行执行，前序产物供后序使用
3. 工程名、音频路径由上下文提供，无需询问用户
4. 单次任务链不超过5个技能"""


class LLMAgent:
    def __init__(self, core: AgentCore, pm: ProjectManager):
        self.core = core
        self.pm = pm

    async def handle(self, user_msg: str, project: str, history: list,
                     audio_path: Optional[str] = None, ws_send=None):
        """主处理：拼上下文 -> 请求LLM -> 分流执行"""
        ctx = self.pm.summary(project) if project else "（未选择工程）"
        user_content = self._build_user_content(user_msg, ctx, history, audio_path)
        messages = [{"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content}]

        # 意图解析用默认模型(skill_ai)
        orchestrator = get_llm("skill_ai")
        try:
            resp = await orchestrator.chat(messages)
        except Exception as e:
            if ws_send:
                await ws_send({"type": "error", "msg": f"LLM请求失败: {e}"})
            await self._rule_fallback(user_msg, project, audio_path, ws_send)
            return

        if not resp:
            await self._rule_fallback(user_msg, project, audio_path, ws_send)
            return

        if ws_send:
            await ws_send({"type": "llm_raw", "msg": resp[:500]})

        task = self._try_parse_task(resp)
        if task and task.get("need_tool"):
            await self._run_chain(task["task_chain"], project, ws_send)
        else:
            if ws_send:
                await ws_send({"type": "text", "msg": resp, "stream": True, "done": True})

    def _build_user_content(self, user_msg, ctx, history, audio_path):
        parts = [ctx, "", f"【历史对话】"]
        for h in history[-6:]:
            parts.append(f"{h.get('role','user')}: {h.get('msg','')}")
        parts.append("")
        parts.append(f"【用户本次需求】\n{user_msg}")
        if audio_path:
            parts.append(f"\n【本地可用素材】\n音频: {audio_path}")
        return "\n".join(parts)

    def _try_parse_task(self, text: str) -> Optional[dict]:
        """从 LLM 输出中提取任务链 JSON"""
        text = text.strip()
        # 去除可能的 markdown 代码块
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        # 找第一个 { 到最后一个 }
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except Exception:
            return None

    async def _run_chain(self, task_chain: list, project: str, ws_send):
        """串行执行任务链。可执行技能走 subprocess, 纯提示词技能走对应模型 LLM"""
        if ws_send:
            await ws_send({"type": "chain_start",
                           "tools": [t.get("tool") for t in task_chain],
                           "chain": task_chain})
        ok = 0; fail = 0
        all_files = []
        for step in task_chain:
            tool = step.get("tool")
            args = step.get("args", {})
            skill_meta = self.core.get_skill(tool) or {}
            is_executable = skill_meta.get("executable", False)

            if ws_send:
                await ws_send({"type": "log", "tool": tool, "msg": f"▶ 开始执行 {tool}"})

            if is_executable:
                # 可执行技能: subprocess
                if project and "project" not in args and "--project" not in args:
                    if any(k in str(skill_meta.get("params", {})).lower() for k in ["--project", "project"]):
                        args["--project"] = project
                result = self.core.run_skill(tool, args, on_log=lambda l: None)
                for log_line in result.get("logs", []):
                    if ws_send:
                        await ws_send({"type": "log", "tool": tool, "msg": log_line})
                status = result["status"]
                files = result.get("files", [])
                err = result.get("error")
            else:
                # 纯提示词技能: 读 SKILL.md, 用该技能自己的模型执行
                status, files, err = await self._run_prompt_skill(tool, args, project, ws_send)

            if status == "ok":
                ok += 1
                all_files.extend(files)
                if ws_send:
                    await ws_send({"type": "skill_done", "tool": tool,
                                   "files": files, "status": "ok"})
            else:
                fail += 1
                if ws_send:
                    await ws_send({"type": "skill_done", "tool": tool,
                                   "files": [], "status": "error", "error": err})
                    await ws_send({"type": "error", "tool": tool, "msg": err or ""})
                break

        if ws_send:
            await ws_send({"type": "chain_done", "total": len(task_chain), "ok": ok, "fail": fail})
            if all_files:
                await ws_send({"type": "text", "msg": f"本次生成产物：\n" + "\n".join(all_files),
                               "stream": True, "done": True})
            await ws_send({"type": "project_updated", "project": project})

    async def _run_prompt_skill(self, tool: str, args: dict, project: str, ws_send):
        """执行纯提示词技能: 读 SKILL.md 当系统提示, 用该技能对应模型调用 LLM。
        返回 (status, files, error)"""
        skill_meta = self.core.get_skill(tool) or {}
        skill_dir = skill_meta.get("dir")
        if not skill_dir:
            return "error", [], f"技能 {tool} 无目录"
        from pathlib import Path
        skill_md = Path(skill_dir) / "SKILL.md"
        if not skill_md.exists():
            return "error", [], f"技能 {tool} 无 SKILL.md"
        skill_text = skill_md.read_text(encoding="utf-8")

        # 用该技能自己的模型
        client = get_llm(tool)
        if not client.api_key:
            return "error", [], f"技能 {tool} 无可用模型配置"

        ctx = self.pm.summary(project) if project else ""
        user_content = f"【工程上下文】\n{ctx}\n\n【技能规范 SKILL.md】\n{skill_text}\n\n【本次参数】\n{json.dumps(args, ensure_ascii=False)}\n\n请按 SKILL.md 规范执行该技能，产出写入工程目录。直接输出技能产物内容。"
        messages = [{"role": "system", "content": f"你是音乐技能 {tool} 的执行器，严格按 SKILL.md 规范产出。"},
                    {"role": "user", "content": user_content}]
        try:
            if ws_send:
                await ws_send({"type": "log", "tool": tool, "msg": f"调用模型({client.model})执行提示词技能..."})
            resp = await client.chat(messages)
            # 把产物写入工程目录 track/{tool}_llm.md
            files = []
            if project and resp:
                out_dir = self.pm.pdir / project / "song_engineer" / "track"
                out_dir.mkdir(parents=True, exist_ok=True)
                out = out_dir / f"{tool}_llm.md"
                out.write_text(f"# {tool} (LLM执行)\n\n{resp}\n", encoding="utf-8")
                files.append(str(out.relative_to(self.pm.pdir)))
            if ws_send:
                await ws_send({"type": "log", "tool": tool, "msg": resp[:300] if resp else "(空)"})
            return "ok", files, None
        except Exception as e:
            return "error", [], f"技能 {tool} LLM执行失败: {e}"

    async def _rule_fallback(self, user_msg: str, project: str, audio_path: Optional[str], ws_send):
        """LLM 不可用时的规则兜底：关键词匹配预设任务链"""
        if ws_send:
            await ws_send({"type": "text", "msg": "（LLM不可用，使用规则匹配执行）", "stream": True, "done": True})
        chain = []
        if audio_path and ("分析" in user_msg or "哼唱" in user_msg or "扒" in user_msg):
            chain.append({"tool": "audio_chord_recognizer", "args": {"input": audio_path}})
        if "mscx" in user_msg or "乐谱" in user_msg or "总谱" in user_msg:
            chain.append({"tool": "musescore-cooperate", "args": {"--project": project, "--full": True}})
        if "混音" in user_msg or "remix" in user_msg.lower():
            chain.append({"tool": "remix-master", "args": {"--project": project}})
        if not chain:
            if ws_send:
                await ws_send({"type": "text", "msg": "无法识别指令，且LLM不可用。可用技能：分析哼唱/生成乐谱/混音。", "stream": True, "done": True})
            return
        await self._run_chain(chain, project, ws_send)