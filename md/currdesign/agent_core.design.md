# AI 模型对接完整结构设计
# 聚焦：AI 模型对接完整结构（只三件事：发什么、收什么、怎么处理）

## 前置边界
运行载体：Electron 前端 + Python 后端；
底层执行：后端内置**简化版 WorkBuddy 也就是 “agent core” ai agent核心**（只负责调用`.workbuddy`音乐技能）；
## 整体分层说明
1. Electron Web前端：用户交互层，负责上传音频、输入文字指令、展示AI回复与工程文件
2. Python后端内部两大独立模块：
   - LLM Agent：专门负责和大模型交互，处理「发送给模型的数据、解析模型返回内容」
   - Agent Core：独立的技能执行内核（原简化版WorkBuddy，改名隔离概念），仅用于本地调用 `.workbuddy` 下所有音乐技能，只接收结构化参数、生成工程文件，无AI理解能力
3. 底层资源：`.workbuddy` 音乐技能库、`workspace/project` 歌曲工程目录

## 完整数据流主干
Electron前端 → WebSocket → Python后端LLM Agent → 调用大模型
LLM返回结果分两条分支：
1. 含技能执行任务 → LLM Agent校验参数 → 调用Agent Core串行运行技能 → 收集产物再请求AI生成总结 → 推送文字/工程更新至前端
2. 纯文字问答内容 → 直接流式推送至前端，不经过Agent Core

# 一、LLM Agent 发给AI模型的完整内容
每次请求统一由三部分拼接组成，使用标准OpenAI兼容messages格式入参大模型
### 1. 固定系统提示词（永久不变）
```
你是音乐创作调度助手，可调用本地音乐技能完成歌曲制作。
1. 可用技能清单与入参规范：
audio_chord_recognizer：参数 audio_path、project_name，读取哼唱音频提取BPM、调性、和弦
ai_chords_master：参数 project_name、style，生成完整歌曲段落和弦进行
muse-lyrics-gen：参数 project_name、rhyme，生成适配和弦的歌词
openutau_lyrics：参数 project_name，输出OpenUTAU专用逐音符歌词文件
song_engineer：参数 project_name，聚合工程全部轨道、生成歌曲诊断与优化建议
2. 输出规则：
- 需要执行技能：仅输出纯净JSON，禁止附带任何解释文字
{
  "need_tool": true,
  "task_chain": [
    {"tool": "技能名称", "args": {参数键值对}}
  ]
}
- 无需执行技能（乐理答疑、旋律点评、文字建议）：直接输出自然中文，不输出JSON
3. 固定执行逻辑：音频分析类技能优先执行；全部生成任务完成后必须追加 song_engineer 收尾聚合工程；工程名、音频路径由上下文提供，无需询问用户。
```

### 2. 动态上下文（每次对话实时拼接）
```
【当前歌曲工程完整文本】
{完整project.md内容}

【历史对话记录】
多轮user/assistant对话记录数组

【用户本次最新需求】
{用户输入的自然语言指令}

【本地可用素材】
音频文件路径：xxx.wav
```

### 3. 标准请求结构体
```python
messages = [
    {"role": "system", "content": 上述固定系统提示词},
    {"role": "user", "content": 动态上下文拼接文本}
]
# 调用大模型接口传入参数 messages
```

# 二、AI模型返回内容 + LLM Agent 处理逻辑
模型返回结果分为两类，LLM Agent分别走独立处理流程
## 类型1：返回技能任务JSON（需要调用Agent Core执行技能）
模型输出示例
```json
{
  "need_tool": true,
  "task_chain": [
    {"tool": "audio_chord_recognizer", "args": {"audio_path":"xxx.wav","project_name":"demo"}},
    {"tool": "ai_chords_master", "args": {"project_name":"demo","style":"沙发小曲"}},
    {"tool": "song_engineer", "args": {"project_name":"demo"}}
  ]
}
```
### LLM Agent处理步骤
1. 参数校验
   - 校验tool名称存在于本地 `.workbuddy` 技能列表；
   - 读取对应技能SKILL.md，校验参数完整性、文件路径合法性；
   校验失败：推送错误消息到前端，终止整个流程。
2. 串行执行任务链
   遍历task_chain内每一项任务，调用Agent Core统一执行接口：
   `result = agent_core.run_skill(tool_name, args)`
   - 执行过程实时推送运行日志、进度信息到前端聊天窗口；
   - 捕获单次技能生成的文件路径、运行日志、异常报错。
3. 任务全部执行完成
   汇总所有生成文件、工程诊断信息，再次发起一次LLM请求，生成通顺的创作总结文案。
4. 推送数据至前端
   - 流式输出AI总结文字；
   - 下发工程更新通知，前端重载右侧工程面板查看新生成md/mid/歌词文件。

## 类型2：返回纯自然中文文本（无需调用Agent Core）
### LLM Agent处理步骤
1. 不进入Agent Core技能执行流程；
2. 将模型文字分段流式推送至前端聊天界面，本轮对话结束。

# 三、Agent Core 核心能力边界（与LLM Agent完全解耦）
1. 唯一对外接口：`agent_core.run_skill(tool_name, args)`
2. 内部能力：
   - 启动时扫描 `.workbuddy` 目录，读取每个技能SKILL.md缓存参数规范；
   - 按传入参数启动对应技能脚本，自动将输出文件写入 `workspace/project/{工程名}/`；
   - 统一返回结构化结果：执行状态、生成文件列表、运行日志、异常信息。
3. 无任何AI相关逻辑，仅作为本地技能执行内核，只接收结构化参数，无法理解自然语言。

# 四、极简完整链路
1. Electron前端上传音频、输入创作指令，通过WebSocket发送：用户文字+音频路径+完整project.md
2. LLM Agent拼接系统提示词+动态上下文，发起大模型请求
3. 大模型返回两类结果：
   - 技能任务JSON：LLM Agent校验参数 → 循环调用Agent Core执行技能 → 汇总产物二次请求AI生成总结 → 推送文字+工程更新给前端
   - 纯文字内容：直接流式下发前端展示
4. 用户手动修改工程MD后，新一轮对话携带最新工程文本重复上述流程