"""llm_agent.py - LLM 意图解析 + 任务链编排 + 串行调度 + 二次总结

LLM 返回两类：
1. 技能任务JSON {need_tool:true, task_chain:[{tool,args}]} -> Agent Core 串行执行
2. 纯文字 -> 直接流式回前端
"""
import json
import re
from typing import Optional

from .agent_core import AgentCore
from .llm_client import llm_client
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

(以下为纯提示词技能，由LLM按SKILL.md执行，不在task_chain中调用脚本)
melody_master / muse-lyrics-gen / muse_ai_master / minimax_music_v3

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

        # 请求 LLM
        try:
            resp = await llm_client.chat(messages)
        except Exception as e:
            if ws_send:
                await ws_send({"type": "error", "msg": f"LLM请求失败: {e}"})
            # 规则兜底
            await self._rule_fallback(user_msg, project, audio_path, ws_send)
            return

        if not resp:
            await self._rule_fallback(user_msg, project, audio_path, ws_send)
            return

        # 调试：推送 LLM 原始输出（截断）
        if ws_send:
            await ws_send({"type": "llm_raw", "msg": resp[:500]})

        # 分流：尝试解析 JSON 任务链
        task = self._try_parse_task(resp)
        if task and task.get("need_tool"):
            await self._run_chain(task["task_chain"], project, ws_send)
        else:
            # 纯文字，流式回前端
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
        """串行执行任务链"""
        if ws_send:
            await ws_send({"type": "chain_start",
                           "tools": [t.get("tool") for t in task_chain],
                           "chain": task_chain})
        ok = 0; fail = 0
        all_files = []
        for step in task_chain:
            tool = step.get("tool")
            args = step.get("args", {})
            # 自动补 project
            if project and "project" not in args and "--project" not in args:
                if any(k in str(self.core.get_skill(tool).get("params", {})).lower() for k in ["--project", "project"]):
                    args["--project"] = project
            if ws_send:
                await ws_send({"type": "log", "tool": tool, "msg": f"▶ 开始执行 {tool}"})

            async def on_log(line, _tool=tool):
                if ws_send:
                    await ws_send({"type": "log", "tool": _tool, "msg": line})

            result = self.core.run_skill(tool, args, on_log=lambda l: None)
            # 同步回调转 async 推送
            for log_line in result.get("logs", []):
                if ws_send:
                    await ws_send({"type": "log", "tool": tool, "msg": log_line})
            if result["status"] == "ok":
                ok += 1
                all_files.extend(result.get("files", []))
                if ws_send:
                    await ws_send({"type": "skill_done", "tool": tool,
                                   "files": result.get("files", []), "status": "ok"})
            else:
                fail += 1
                if ws_send:
                    await ws_send({"type": "skill_done", "tool": tool,
                                   "files": [], "status": "error", "error": result.get("error")})
                    await ws_send({"type": "error", "tool": tool, "msg": result.get("error", "")})
                break  # 失败中断

        if ws_send:
            await ws_send({"type": "chain_done", "total": len(task_chain), "ok": ok, "fail": fail})
            if all_files:
                await ws_send({"type": "text", "msg": f"本次生成产物：\n" + "\n".join(all_files),
                               "stream": True, "done": True})
            await ws_send({"type": "project_updated", "project": project})

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