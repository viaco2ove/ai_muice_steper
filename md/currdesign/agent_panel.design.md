# ai agent 设计。简化版的“WorkBuddy” 类ai 智能体
# 简化到什么程度
# 一、先统一核心定义：你的Electron桌面端 = 简化版自研WorkBuddy
这里完全抛开腾讯同名软件，只以你项目里 **`.workbuddy/` 技能体系** 为基准：
原生完整WorkBuddy（你现有CLI形态）能力：
1. 批量执行任意技能、多技能串行/并行调度
2. 读取各技能`SKILL.md`元信息、入参/输出规范校验
3. 文件路由：自动绑定`workspace`工程目录读写
4. 无状态单次执行，仅靠参数传递数据
5. 无内置长上下文、无工程状态记忆、无对话交互

Electron客户端本质是**带可视化GUI、工程状态上下文、LLM对话调度的简化定制分支**，是简化版，简化取舍逻辑：
砍掉通用无关能力，只保留音乐创作刚需能力，新增音乐专属上层逻辑（工程MD、歌曲迭代Agent）。

# 二、简化取舍：原生WorkBuddy 哪些能力保留、哪些砍掉
## 保留（必须底层复用，不重做）
1. 技能统一执行入口 `run_skill(技能名, 参数)`
   直接读取 `.workbuddy/xxx/SKILL.md` 校验入参、运行技能脚本、输出文件到`workspace`
2. 所有音乐技能原样不动：和弦识别、歌词生成、旋律优化、OpenUTAU歌词、MIDI/mscx导出、混音
3. 技能标准输入输出契约：文件路径、工程名、配置参数规范完全沿用
4. 日志输出体系：技能运行日志可捕获推送到前端界面

## 砍掉（通用冗余能力，简化瘦身）
1. 通用非音乐类技能支持（FTP等无关工具直接移除调度列表）
2. 多工作空间并行、远程任务、批量队列、分布式执行（只保留本地单任务串行）
3. 复杂权限、多用户、云端缓存、远程技能仓库（仅本地离线运行）
4. 通用YAML配置、多环境兼容、插件热加载（固定一套音乐技能集）

## 新增（简化版独有上层增强，原生CLI没有）
1. LLM Agent 自然语言意图拆解，自动编排技能执行链
2. 以`project.md`为核心的工程持久上下文（原生WorkBuddy无状态）
3. 双向同步：前端手动修改MD后，上下文自动更新给AI
4. 可视化进度、音频/MIDI预览、一键导出配套创作素材
5. 自动后置执行`song_engineer`做工程聚合诊断

# 三、够用级简化版WorkBuddy（Electron配套后端）必备核心能力
## 能力1：技能元数据自动扫描与校验
1. 启动时遍历 `.workbuddy/`，读取每个技能`SKILL.md`，缓存技能名称、触发词、入参、输出目录
2. 调用技能前自动校验参数类型、文件是否存在、工程目录是否创建
3. 对外暴露接口：获取全部可用音乐技能列表，前端渲染按钮/指令模板

## 能力2：单技能独立执行（基础兜底功能）
用户不想用AI自动编排时，可以手动选择单个技能、填参数执行，等价于可视化CLI。
示例：单独上传音频执行和弦识别、单独生成歌词、单独导出OpenUTAU歌词。

## 能力3：多技能串行流水线调度（Agent核心底层）
支持按顺序执行一组技能，捕获每一步输出产物作为下一步输入，自动绑定同一歌曲工程。
例如：音频分析→和弦生成→旋律优化→歌词生成，全程自动传递工程名、音频路径，无需用户重复填参数。

## 能力4：全链路日志捕获与实时推送
技能控制台输出、报错、进度信息实时通过WebSocket推送到Electron聊天界面，用户能看清AI正在执行哪一步、有无报错。

## 能力5：工程目录自动管理（绑定workspace/project）
1. 创建工程自动生成文件夹、初始化空白`project.md`
2. 所有技能输出强制隔离到对应工程目录，不会文件混乱
3. 提供接口读取工程内所有轨道MD、MIDI、音频、歌词文件给前端渲染

## 能力6：文件读写与产物分发接口
封装统一文件接口：
- 上传音频/ midi 存入工程res目录
- 读取生成的mid、txt、mscx、wav 返回前端预览/下载
- 前端编辑MD后，覆盖写入本地`project.md`

## 能力7：对接LLM Agent的任务转换能力（简化版核心特色）
原生WorkBuddy只能接收结构化参数；简化版新增一层转换：
接收自然语言对话 → LLM输出标准化技能任务链 → 调度层自动循环调用run_skill。
这是GUI工具区别于纯CLI的核心价值。

## 能力8：内置song_engineer自动收尾
任意流水线执行完毕后，自动调用工程聚合诊断技能，更新工程MD的诊断、优化建议区块，形成闭环。

# 四、最低可用简化版 分层最小结构（Electron配套Python后端）
```
# 简化版WorkBuddy调度层（仅音乐专用）
music_scheduler/
├── skill_scanner.py    # 扫描.workbuddy 读取SKILL.md
├── skill_runner.py     # 封装run_skill，执行单技能、捕获日志
├── pipeline_builder.py # 多技能串行流水线构造
├── project_manager.py  # workspace工程目录、MD读写
├── agent_task_adapter.py # LLM自然语言 → 技能任务转换器
└── file_service.py     # 音频/MIDI/歌词文件上传下载
```
# 五、区分两个层级的“够用标准”
## 层级1：极简够用（仅可视化外壳，无AI对话）
适合只想替代命令行，手动点按钮跑技能：
必备能力：技能扫描、单技能执行、工程文件管理、日志展示、文件导出。
属于**轻度简化WorkBuddy**，无Agent，无自动流水线。

## 层级2：完整创作工作台（你需要的最终形态，带AI Agent）
在极简基础上增加：流水线调度、LLM任务转换、工程上下文持久化、自动聚合诊断。
是**带AI增强的定制简化WorkBuddy**，满足哼唱→AI全流程创作需求。

# 六、总结一句话
1. 它本质就是**音乐垂直领域的简化自研WorkBuddy**，砍掉通用无关功能，保留全部音乐技能执行底座；
2. 最低够用底线：能扫描、单独运行任意技能、管理工程文件、展示日志；
3. 完整创作够用标准：额外支持AI自动编排多技能流水线、绑定工程MD上下文、自动聚合诊断歌曲工程。

# 架构设计
# 一、先定核心结论
1. Electron+Web 整体程序 = **带GUI、带LLM对话、带工程上下文的定制简化版自研WorkBuddy**
   基准：你本地 `.workbuddy` 是纯CLI、无界面、无LLM、无持久工程状态的原生技能执行系统；Electron方案是它的上层简化定制分支，砍掉通用无关能力、只保留音乐技能，新增界面/AI/工程管理。
2. AI Agent 分为两层：
   - 前端交互Agent（Web界面，只负责对话展示、指令转发）
   - 后端调度Agent（Python FastAPI内部，真正负责解析自然语言、编排、调用 `.workbuddy` 技能）
3. 界面不直接跑技能，所有技能执行全部交给后端封装的 `workbuddy` 调度器。

# 二、整体分层架构（Electron + Web前端 + Python后端 + .workbuddy技能库）
## 四层结构自上而下
```
1. Electron 渲染进程（React Web界面）——前端交互Agent
    ↓ HTTP/WebSocket 消息
2. Electron 主进程(Node.js)——进程托管、本地文件权限中转
    ↓ 转发请求到本地Python服务端口
3. Python FastAPI 后端（核心调度层 = 简化版WorkBuddy内核 + AI调度Agent）
    ├ AI调度Agent模块（LLM意图解析、任务链编排）
    ├ 简化WorkBuddy封装层（扫描/执行.workbuddy下所有音乐技能）
    ├ 工程管理器（读写project.md、workspace工程目录）
4. 底层资源
    ├ .workbuddy/ 全部音乐技能（audio_chord_recognizer、muse-lyrics-gen…）
    └ workspace/project/ 歌曲工程存储目录
```

## 1）Electron渲染层（Web界面，前端交互Agent）
界面布局：左侧AI对话窗口、右侧音乐工程工作台
### 前端Agent职责（只做交互，不运算、不执行技能）
1. 接收用户输入：自然语言创作指令、上传哼唱音频、手动编辑工程MD文本
2. 基础参数校验：文件格式、工程名称、BPM/风格等
3. 通过WebSocket把「用户文字+附件」发送给后端Python服务
4. 流式接收后端推送：AI回答、技能运行日志、工程更新通知、进度
5. 可视化渲染：和弦表格、分轨列表、音频播放器、MIDI预览、MD编辑器
6. 触发导出：请求后端生成mid/lyrics.txt/mscx，下载到本地

### 通信方式
- 实时对话、技能进度、日志推送：WebSocket `ws://127.0.0.1:8000/ws/chat`
- 文件上传、保存MD、导出文件：HTTP GET/POST接口

## 2）Electron主进程（Node.js，桥梁层）
1. 程序启动时自动拉起Python FastAPI后台子进程，后台静默常驻
2. 权限隔离：Web前端无法直接读写本地磁盘，所有文件操作请求转发Python后端处理
3. 进程保活：Python服务异常自动重启；关闭Electron时销毁Python进程
4. 系统能力：麦克风录音、打开本地文件夹、唤起MuseScore/OpenUTAU

## 3）Python后端：两大核心模块（重点）
### 模块A：简化版WorkBuddy封装层（对应你原生.workbuddy CLI能力）
只保留音乐创作相关能力，砍掉FTP等无关技能，提供统一执行入口：
1. 启动扫描 `.workbuddy/`，读取每个技能的`SKILL.md`，缓存技能名、入参、输出路径
2. 统一执行函数 `run_music_skill(skill_name, params)`
   - 校验参数合规性
   - 调用对应技能脚本运行
   - 捕获控制台日志、报错，实时推送到前端
   - 技能产物自动输出到 `workspace/project/{工程名}/`
3. 支持两种调用模式：
   - 手动单技能执行（界面按钮单点触发）
   - 批量串行流水线（AI自动编排多技能连续执行）

> 这一层就是**简化版WorkBuddy本体**，复用你全部原有技能，仅精简无关功能、增加接口化调用能力。

### 模块B：AI调度Agent（串联自然语言与WorkBuddy调度层）
这是CLI原生WorkBuddy没有的新增上层逻辑，完整工作流程：
1. 接收前端传来的用户自然语言指令+工程上下文（当前project.md全部内容）
2. 调用LLM做意图识别，输出结构化任务链：
   ```json
   {
     "task_chain": ["audio_chord_recognizer", "ai_chords_master", "muse-lyrics-gen"],
     "global_params": {"project_name": "demo", "audio_path": "xxx.wav", "style": "沙发小曲"}
   }
   ```
3. 循环调用简化WorkBuddy封装层的`run_music_skill`，按顺序执行整条流水线
4. 每一步执行完成，自动刷新工程文件；全链路结束强制调用`song_engineer`聚合、诊断工程
5. 把分析点评、优化建议、运行日志通过WebSocket回流前端界面

# 三、完整实操流程演示（界面如何联动技能）
1. 用户打开Electron客户端，Node主进程自动启动Python后端服务；
2. 左侧聊天面板上传哼唱wav，输入指令：“分析这段哼唱，生成沙发小曲完整主歌副歌，生成歌词并导出OpenUTAU歌词文件”；
3. 前端Agent打包音频+文字指令，通过WebSocket发送到Python后端AI调度Agent；
4. AI Agent调用大模型拆解出技能执行序列；
5. AI Agent循环调用【简化版WorkBuddy封装层】，依次执行：
   `audio_chord_recognizer` → `ai_chords_master` → `muse-lyrics-gen` → `openutau_lyrics`；
6. 每一个技能运行的实时日志同步推送到左侧聊天窗口；
7. 流水线全部执行完毕，自动执行`song_engineer`聚合所有轨道、生成工程诊断报告写入project.md；
8. 后端推送「工程已更新」信号，前端自动重载右侧工作台，展示和弦、歌词、生成好的MIDI与歌词文件；
9. 用户在右侧手动修改MD和弦/歌词，保存后再次发指令“优化副歌旋律，增加转音”；
10. AI Agent读取最新工程MD作为上下文，再次调度`melody_master`迭代优化。

# 四、回答核心问题：这套Electron程序 是否等同于简化版workbuddy？
## 1. 底层内核：是的，它就是定制简化版WorkBuddy
原生CLI `.workbuddy` 能力：
- 扫描技能元数据、执行技能、文件输出、日志捕获
简化版后端完全保留以上核心能力，同时做两处精简：
1. 删除FTP等非音乐类技能调度逻辑；
2. 移除分布式、多用户、远程仓库等复杂通用功能，仅本地单任务串行执行。
所以**Python后端的技能调度模块 = 音乐专用简化WorkBuddy**。

## 2. 完整Electron应用 ≠ 单纯简化WorkBuddy，是「简化WorkBuddy + AI Agent + GUI外壳」的复合产品
原生CLI WorkBuddy缺失三大能力，Electron整套程序额外叠加：
1. LLM自然语言理解、自动编排多技能流水线的AI Agent；
2. 可视化Web界面、聊天交互、音频/MIDI预览；
3. 以project.md为核心的持久工程上下文、多轮人工+AI迭代闭环。

## 3. 两种场景区分
1. 只做界面按钮、手动单点触发技能、无LLM自动编排：
   此时整个程序可视作**可视化简化版WorkBuddy**；
2. 加入AI Agent自然语言自动串联多条技能、工程持续迭代：
   底层调度内核仍是简化WorkBuddy，但整体应用是独立AI音乐工作台，不止单纯封装技能工具。

# 五、极简总结
1. Electron Web界面仅负责展示与收发指令，**不直接调用任何技能**，全部交给本地Python后端；
2. Python后端内部有一层独立封装模块，是**针对音乐场景精简后的自研WorkBuddy**，负责扫描、运行你所有`.workbuddy`技能；
3. AI Agent运行在Python后端，负责把人话翻译成技能执行流程，驱动简化WorkBuddy批量执行任务；
4. 内核调度层等价简化版WorkBuddy；完整Electron客户端是在简化WorkBuddy之上叠加AI对话与可视化界面的完整创作工具。


# 故根究底就是  如何对接 ai模型 ，发送什么，如何处理返回结果。
[agent_core.design.md](agent_core.design.md)