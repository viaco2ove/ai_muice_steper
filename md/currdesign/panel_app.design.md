# 完整落地方案：基于现有 `.workbuddy` 技能，开发 Web / Desktop AI音乐工程工作台
你现有基础：Python 技能集（和弦识别、旋律提取、歌词生成、MIDI、OpenUTAU歌词、mscx、混音、song_engineer工程中枢）、**工程MD为唯一数据源**、WorkBuddy技能调度层。
分两条路线：**Web网页端（优先，开发成本低、跨平台）**、**Desktop桌面客户端（本地离线强需求）**，共用同一套后端Python技能，只换前端层。

## 一、整体架构统一设计（Web/Desktop共用底层，复用你全部技能）
### 分层结构（完全复用现有 `ai_muice_steper`）
```
┌─────────────────────────────────────────────────────┐
│  上层交互层（二选一：Web前端 / Desktop客户端）        │
│  - 聊天Agent对话窗口：自然语言下发创作指令            │
│  - 工程MD可视化编辑器：和弦/轨道/歌词预览、手动编辑    │
│  - 音频上传/录音、MIDI预览、文件导出面板             │
└───────────────────────┬─────────────────────────────┘
                         │ HTTP接口调用
┌─────────────────────────▼─────────────────────────────┐
│  Python统一后端服务（FastAPI，核心调度层）              │
│  1. 工程文件管理：读写 workspace/project/* 工程MD      │
│  2. WorkBuddy技能调度器：调用所有.skills音乐能力       │
│  3. LLM Agent封装：接收自然语言，拆解成技能任务        │
│  4. 文件接口：返回MIDI、txt歌词、mscx、音频文件        │
│  5. MD解析/序列化工具：md-parser，前后端数据互通       │
└───────────┬───────────────────┬───────────────────────┘
            │                   │
┌───────────▼───────┐ ┌─────────▼─────────────────────┐
│ .workbuddy 技能池 │ │ workspace/ 工程存储目录        │
│ audio_chord_recognizer │ project/{song}/project.md  │
│ muse-lyrics-gen       │ track/*.md、ai-track/*.mid  │
│ openutau_lyrics       │ 哼唱音频、导出wav/mscx      │
│ melody_master / song_engineer / remix-master 等     │
└───────────────────┘ └─────────────────────────────┘
```

### 核心逻辑：AI Agent如何参与音乐工程
1. 用户在界面输入自然语言指令（如“分析这段哼唱，生成完整主歌副歌和弦，写适配歌词”）
2. 后端LLM Agent解析意图，自动串行调用技能：
   `audio_chord_recognizer` → `ai_chords_master` → `muse-lyrics-gen` → `melody_master`
3. 所有技能输出全部写入对应工程目录下的 `track/*.md`、`ai-track/*.mid`
4. `song_engineer` 自动聚合全部半成品，写入 `project.md` 做统一工程汇总、五维诊断、给出优化建议
5. 前端实时加载更新后的工程MD，可视化展示和弦、旋律、歌词；用户可手动修改MD，再次让AI优化迭代
6. 最终导出产物：MIDI、OpenUTAU歌词txt、mscx乐谱、伴奏音频、混音成品wav

## 二、方案1：Web网页端（推荐，开发最快、无需打包客户端）
### 1. 技术栈（复用你技术栈.md规范）
- 后端：Python FastAPI（统一调度WorkBuddy技能）
- 前端：React18 + TS + Vite + Tailwind + shadcn/ui
- 通信：HTTP（文件上传/接口请求）+ WebSocket（实时工程更新、AI流式回复）
- 部署：本地一键启动 `docker-compose up`，浏览器打开 `http://127.0.0.1:5173`

### 2. 前端页面核心分区（匹配你「左侧Agent对话+右侧工程工作台」设计）
#### 左侧：AI Agent聊天面板
- 录音/上传哼唱音频按钮
- 对话输入框：自然语言下达创作、修改、优化指令
- AI流式输出：旋律分析、和弦点评、歌词、工程诊断建议
- 快捷指令模板：生成副歌、丰富和弦、优化转音、导出OpenUTAU素材

#### 右侧：音乐工程工作区
1. 工程基础信息面板：调性/BPM/风格/情绪
2. 段落可视化表格：前奏/主歌/预副歌/副歌/桥段和弦总览
3. 分轨编辑器：01和弦、02主唱、03吉他等轨道MD在线编辑
4. 预览区：和弦播放、MIDI简易波形预览、音频播放
5. 导出按钮：MIDI、mscx、OpenUTAU歌词txt、伴奏wav

### 3. 后端关键接口（打通所有技能）
1. 工程管理接口
   - `POST /api/project/new`：新建歌曲工程，生成project.md骨架
   - `GET /api/project/{name}`：读取工程MD，解析为JSON传给前端渲染
   - `PUT /api/project/{name}`：前端手动编辑MD后，写回本地文件
2. 音频分析接口
   - `POST /api/audio/analyze`：上传哼唱wav，调用`audio_chord_recognizer`，输出旋律、和弦写入工程
3. 技能调度接口（Agent自动调用，也可手动触发）
   - `/api/skill/chords`：ai_chords_master 丰富和弦段落
   - `/api/skill/lyrics`：muse-lyrics-gen 生成歌词
   - `/api/skill/melody`：melody_master 优化主旋律
   - `/api/skill/openutau-lyric`：导出音符对齐歌词txt
   - `/api/skill/mscx`：musescore-cooperate 生成mscx总谱
4. Agent对话接口
   - `WS /api/chat`：WebSocket流式对话，LLM自动规划技能调用链路，实时回写工程文件

### 4. 启动流程（零改造现有技能）
1. 在 `ai_muice_steper/backend/` 编写FastAPI服务，内置WorkBuddy调用函数，直接读取`.workbuddy`下所有技能
2. 前端打包后放入 `frontend/dist`，后端静态托管
3. 执行 `docker-compose up` 启动前后端一体服务
4. 浏览器访问即可，所有生成文件自动落到原有 `workspace/project/` 目录，完全兼容现有文件结构

## 三、方案2：Desktop桌面客户端（离线本地优先，适合无网络场景）
两条实现路径，从轻量到重型：
### 路径A：轻量Electron（最简，复用Web前端代码）
1. 直接把上面整套React Web前端打包进Electron壳子
2. Electron内置Python FastAPI后端进程，开机自动启动
3. 优势：90%前端代码和Web端共用，只加桌面窗口、本地文件系统权限、打包exe
4. 适配Windows，你的AMD主机本地离线运行，无需浏览器

### 路径B：原生Python桌面（PyQt6，纯Python栈，无前端JS）
适合不想写React，全Python开发：
1. UI层：PyQt6 分栏布局（左侧对话、右侧MD编辑器）
2. 内置子进程调用WorkBuddy技能，本地文件读写`workspace`
3. 内置简易音频播放器、MIDI预览、SF2 FluidSynth试听
4. 打包：`pyinstaller` 一键打包成独立exe，自带Python虚拟环境、所有技能依赖

### Desktop独有能力
1. 本地文件拖拽：直接拖拽哼唱音频、MIDI进工程
2. 本地录音麦克风直录，无需网页权限
3. 离线完整运行：LLM可切换本地大模型，不依赖外网API
4. 关联本地OpenUTAU、MuseScore、FluidSynth，一键打开生成的mid/mscx

## 四、核心打通逻辑：如何让AI Agent调度你现有的所有技能
### 1. 封装统一技能调用函数（后端Python）
写一层通用包装，后端可任意调用任意`.workbuddy`技能：
```python
from workbuddy import run_skill

# 示例：哼唱音频分析
def analyze_hum(audio_path, project_name):
    result = run_skill("audio_chord_recognizer", audio=audio_path, target_project=project_name)
    # 技能自动输出md/mid到workspace/project/{project_name}/
    return result
```
所有技能输出路径完全沿用你现有`workspace`目录结构，不用改动原有技能代码。

### 2. LLM Agent任务拆解逻辑
用户输入一句话，大模型识别需求，自动编排技能执行顺序：
示例用户输入：
> 上传哼唱，生成完整民谣主歌副歌，写押韵歌词，导出OpenUTAU歌词和吉他MIDI

Agent拆解执行链：
1. `audio_chord_recognizer` 提取旋律、BPM、调性
2. `ai_chords_master` 生成完整段落和弦
3. `melody_master` 优化主旋律，生成主唱MIDI
4. `muse-lyrics-gen` 生成匹配和弦韵律歌词
5. `openutau_lyrics` 生成逐音符歌词txt
6. 调用song_engineer聚合全部内容，诊断工程给出优化建议
7. 生成吉他分解MIDI轨道存入ai-track

### 3. 双向同步机制（人工编辑 ↔ AI迭代）
1. 用户在前端手动修改右侧工程MD（和弦、歌词、旋律段落），保存写入本地文件
2. 再次和AI对话时，Agent自动读取最新`project.md`作为上下文，基于当前修改继续优化
3. song_engineer持续维护工程状态，记录每一次AI生成/人工修改日志，形成迭代闭环

## 五、分阶段落地步骤（低成本渐进开发，不用一次性写完）
### 阶段1：搭建Python FastAPI后端（1-3天，核心底座）
1. 封装WorkBuddy技能调用接口
2. 实现工程MD读写、解析、序列化工具
3. 完成基础文件接口：上传音频、生成MIDI、导出txt歌词
4. 本地curl/postman测试全部技能可正常调用，输出到原有workspace目录

### 阶段2：Web最小可用前端（3-5天，快速验证产品形态）
1. 左右分栏基础布局：左侧聊天、右侧MD预览
2. 实现音频上传、工程切换、基础导出功能
3. WebSocket对接AI对话，实现流式回复
4. 完成完整链路：哼唱上传 → AI生成和弦歌词 → 前端预览工程

### 阶段3：功能完善（持续迭代）
1. 和弦可视化、简易音频/MIDI播放器
2. 在线MD编辑器，支持手动修改轨道内容
3. 批量导出mscx、分轨wav、混音功能对接remix-master
4. 增加工程版本简易记录、AI一键诊断优化

### 阶段4（可选）：打包Desktop客户端
基于完成的Web前端套Electron，或重写PyQt6桌面程序，打包exe分发本地离线使用

## 六、适配你现有创作流程的配套优势
1. 完全兼容你现有的工具链：
   - 生成mid → FluidSynth + SF2吉他渲染伴奏
   - 生成lyrics.txt → OpenUTAU DiffSinger导入渲染人声，规避AMD核显GRU崩溃
   - 生成mscx → MuseScore精细打谱编辑
2. 工程MD统一管理所有素材，所有AI生成内容有序归档，不会散落文件
3. AI全程参与全流程：扒谱、编和弦、写歌词、优化旋律、诊断工程、批量导出生产素材，形成完整创作闭环