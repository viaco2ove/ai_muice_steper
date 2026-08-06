# AGENTS.md

This file provides guidance to Qoder (qoder.com) when working with code in this repository.

## What this is

AI 音乐创作工作台：哼唱/构思 → AI 编排技能生成和弦/旋律/歌词 → 工程MD（唯一真相源）→ 持续迭代 → 导出 MIDI/mscx/混音。

两层实现：
1. **`.workbuddy/skills/`** — Python 音乐技能（CLI 形态，每个有 `SKILL.md` + `scripts/`），独立可用。
2. **`backend/` + `frontend/`** — Web 工作台：FastAPI 后端（Agent Core 调度技能 + LLM Agent 编排）+ React 前端（左对话 / 右工程）。

## Commands

### 启动工作台
```bash
# Windows 一键（开两个窗口）
start_workbench.bat

# 或手动
cd backend && .venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
cd frontend && npm run dev          # http://127.0.0.1:5173
```
后端 API 文档：http://127.0.0.1:8000/docs

### 前端
```bash
cd frontend
npm install
npm run dev      # dev server (vite, 代理 /api 和 /ws 到 :8000)
npx tsc --noEmit # 类型检查
npm run build    # 产物到 frontend/dist (后端会静态托管)
```

### 直接跑技能脚本（不经工作台）
技能脚本用**主 `.venv`**（含 librosa/mido/demucs 等），不是 `backend/.venv`：
```bash
.venv/python.exe .workbuddy/skills/musescore-cooperate/scripts/mscx_generator.py --project 走在 --full --bpm 68
```

## Two-venv setup（关键，易踩坑）

- **`.venv/`**（根）— 技能脚本运行环境：librosa, mido, numpy, demucs, torch...。`backend/app/config.py` 的 `PYTHON_EXE` 指向它，Agent Core 用 `subprocess` 调技能时走这个解释器。
- **`backend/.venv/`** — 后端服务环境：fastapi, uvicorn, httpx, pydantic, pyyaml, python-dotenv。**不要**把后端依赖装进根 `.venv`（会与 torch/demucs 冲突，曾导致 anyio/click 损坏）。

安装后端依赖：`backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt`

## Architecture

### 数据流（工作台模式）
```
React(5173) ─proxy─► FastAPI(8000)
   WS /ws/chat           ├─ LLMAgent: 自然语言 → 任务链JSON → 串行调度
   REST /api/*           ├─ AgentCore: subprocess 调 .workbuddy 技能(用根.venv)
                         └─ ProjectManager: 读写 song_engineer.json
```

### 工程数据模型（唯一真相源 = `workspace/project/{歌名}/`）
```
workspace/project/{歌名}/
├── project.md                      # 原始雏形（只读，song_engineer 不改）
├── song_engineer/                  # ★ 工作台主数据源
│   ├── song_engineer.json          # 机器读写镜像（前后端双向同步）
│   └── track/{NN_轨名}.md + .json  # 分轨（每轨独立，支持单轨迭代）
└── *.mid *.wav *.mscx lyrics.txt   # 技能产物附件
```
- `song_engineer` 技能是天然的聚合/诊断层，工作台直接复用其 md+json 产物，不重造。
- 前端编辑轨道 MD → `PUT /api/project/{name}/track/{id}` → 后端写 md 并重解析生成 json（双向同步）。
- LLM 每轮对话前，`ProjectManager.summary()` 读 `song_engineer.json` 精简摘要拼进上下文。

### Agent Core ↔ LLM Agent 协议
LLM 输出两类（系统提示词见 `backend/app/core/llm_agent.py:SYSTEM_PROMPT`）：
1. **任务链JSON** `{"need_tool":true,"task_chain":[{"tool","args"}]}` → AgentCore 串行 `run_skill()` subprocess 执行，日志实时推 WS。
2. **纯文字**（乐理答疑/点评）→ 直接流式回前端。
- LLM 不可用时自动**规则兜底**（关键词匹配→预设技能链）。
- 默认 LLM 是本地模型 `orcg`（`http://127.0.0.1:3428/v1`，OpenAI 兼容协议），配置在 `models.json` / `.env` 的 `LLM_*`。

### 技能契约（`.workbuddy/skills/*/SKILL.md` frontmatter）
每个技能 SKILL.md 含：`name` `description` `entry_script`（相对路径，如 `scripts/mscx_generator.py`）`params`（JSON）`executable`（bool）。
- `executable: true` — 有 argparse 脚本，Agent Core 直接 subprocess 调，参数 dict→CLI flags（`--project 走在 --tracks "01_吉他"`）。
- `executable: false` — 纯提示词技能（melody_master/muse-lyrics-gen 等），靠 LLM 按 SKILL.md 执行，**不能** subprocess 调。
新增技能时务必补全 frontmatter 这几个字段，否则 Agent Core 扫不到/调不了。

### LLM 多模型路由
`models.json` 定义可用模型列表（id/url/apiKey/model），`skill_ai` 指定默认模型，各 skill 可覆盖。`llm_client.py` 的 `LLMRegistry` 按 skill 名解析对应 `LLMClient`，支持技能级模型隔离。

## Conventions

### 特别注意
不允许在 workspace 下 写python代码,如果有临时代码需求 写到 .cache/temp/ ！！！

### 终端编码
Windows 终端是 GBK，Python `print` 中文/emoji 会 `UnicodeEncodeError`。脚本里加 `sys.stdout.reconfigure(encoding='utf-8')`；测试输出中文时用 `python -X utf8`。

### 音符数据格式（3 种，`mscx_generator.load()` 已兼容）
轨道 JSON 的 notes 有三种来源格式，都已被 loader 处理：
1. `bars[].beats[]`（01_吉他等，含和弦/指法）
2. `notes[]` 数组（02_主唱/13_轻贝斯等，含 `beat_pos`）
3. MIDI 文件 fallback（量化到 60-tick/32nd 网格）
- `beat_pos` 有两段（`拍.子拍`，如 `2.1`）和三段（`小节.拍.子拍`，如 `1.2.1`）两种，`_pos()` 会区分，改解析时注意别混。
- 打击乐轨（14_slap）的 `actual` 存 GM note number 字符串（如 `"38"`），loader 有 midi 字段 fallback。

### 时值校验
mscx 生成后必须保证每小节 = 1920 ticks (4/4)。`measure_xml()` 用 timeline 铺满逻辑（补休止符、截断溢出、同时刻音符合并为和弦）。改完生成器务必跑时值校验：
```bash
.venv/python.exe -c "import re;xml=open('.../x.mscx',encoding='utf-8').read(); ..." # 见 .cache 历史
```

### MuseScore 4.7 容器格式
`musescore-cooperate` 生成的是容器目录（不是单个 mscx）：`{歌名}/{歌名}.mscx` + `audiosettings.json`（音色配置，MuseSounds UID）+ `META-INF/container.xml`。音色配置**不在 .mscx 里**，在 audiosettings.json 的 `tracks[].in.resourceMeta`。改音色改 `musescore.conf.json` 的 `museUID`/`museName` 后重跑生成器。

## Key files

| 文件 | 作用 |
|------|------|
| `backend/app/core/agent_core.py` | 技能扫描/subprocess执行/日志捕获/产物收集 |
| `backend/app/core/llm_agent.py` | 系统提示词/意图解析/任务链调度/规则兜底 |
| `backend/app/core/project_manager.py` | 工程 json 读写/轨道CRUD/LLM上下文摘要 |
| `backend/app/core/llm_client.py` | OpenAI兼容协议封装/技能级模型路由 |
| `backend/app/core/md_parser.py` | 轨道/工程MD解析与序列化（前后端共用逻辑） |
| `backend/app/main.py` | FastAPI 入口 + WS `/ws/chat` + 静态托管 |
| `backend/app/config.py` | 后端配置，读 .env + models.json |
| `.workbuddy/skills/musescore-cooperate/scripts/mscx_generator.py` | mscx 生成器（字符串拼接法，含音色配置生成）|
| `.workbuddy/skills/song_engineer/SKILL.md` | 工程聚合/诊断中枢规范 |
| `workspace/project/走在/song_engineer/musescore/musescore.conf.json` | 分轨音色配置（MuseSounds UID 映射）|
| `md/currdesign/` | 设计文档（技术栈/工程MD格式规范/agent设计）|
| `.cache/plan/` | 工作台落地规划（8 分册）|

## Local tooling

- MuseScore 4.7 + MuseSounds 全套库（`C:\Users\viaco\Muse Hub\Instruments`），渲染走 `MuseScore4.exe -f --sound-profile MuseSounds -o out.mp3 in.mscx`。
- FluidSynth + MS Basic.sf3（`/c/Program Files/MuseScore 4/sound/`）。
- `.env` 含 `minimax_api_key`（音乐生成）、`fluidsynth_path`、`musescore_ver`。
