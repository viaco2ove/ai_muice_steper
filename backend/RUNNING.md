# AI音乐工程工作台 · 运行说明

## 快速启动
双击 `start_workbench.bat`，或手动：
```bash
# 终端1 - 后端
cd backend
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# 终端2 - 前端
cd frontend
npm run dev
```
- 前端: http://127.0.0.1:5173
- 后端: http://127.0.0.1:8000  (API文档: http://127.0.0.1:8000/docs)

## 环境配置
### .env (项目根)
```
LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/v3   # OpenAI兼容协议
LLM_API_KEY=sk-xxx                                       # 豆包/通义 key
LLM_MODEL=doubao-pro-32k
PYTHON_EXE=.venv/python.exe                              # 技能脚本用主venv
```
> 不配 LLM key 也能用：自动回退规则匹配（关键词触发预设技能链）。

### 两个 venv
- `backend/.venv` - 后端 FastAPI 依赖（fastapi/uvicorn/httpx/pyyaml）
- `.venv` - 技能脚本依赖（librosa/mido/demucs...），Agent Core 调技能时用 `config.python_exe` 指向它

## 已完成
- ✅ 技能契约: 15个技能 SKILL.md 加 entry_script/params/executable
- ✅ 后端: FastAPI + Agent Core + Project Manager + LLM Agent + WS
- ✅ REST: /api/skills /projects /project /skill /audio /export
- ✅ WebSocket: /ws/chat (对话+日志+技能执行流式推送)
- ✅ 前端: React+TS+Tailwind+Zustand 左右分栏 (ChatPanel + WorkspacePanel)
- ✅ 验证: WS对话触发 musescore-cooperate 生成10轨mscx，日志实时推送

## 核心架构
```
前端(5173) ──proxy──► 后端(8000)
   │                    ├ Agent Core (subprocess调.workbuddy技能)
   │ WS /ws/chat        ├ LLM Agent (OpenAI协议, 规则兜底)
   └────────────────►   └ Project Manager (读song_engineer.json)
```

## 验证过的链路
1. `GET /api/health` -> {ok:true, skills:15, projects:1}
2. `GET /api/skills` -> 6可执行 + 9纯提示词
3. `POST /api/skill/musescore-cooperate` -> 执行技能返回日志
4. `WS /ws/chat` "生成01_吉他乐谱" -> 规则匹配->musescore-cooperate->10轨mscx生成->project_updated

## 待完善
- [ ] LLM key 配置后测真实意图解析（任务链JSON）
- [ ] 前端 TrackEditor 在线MD编辑
- [ ] 前端 ChordViz 和弦可视化
- [ ] 音频/MIDI 预览组件
- [ ] Desktop 打包(Electron)