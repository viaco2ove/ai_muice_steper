---
name: song_engineer
description: 歌曲工程聚合、诊断与优化技能。用于初始化/聚合歌曲工程MD、诊断半成品完成度与一致性、给出优化建议并辅助教学。触发词：诊断工程、优化歌曲、看现状、下一步怎么改、继续打磨、工程体检、初始化工程、聚合半成品、工程初始化。
agent_created: true
entry_script: "scripts/export_track_to_midi.py"
params: {"input": "输入JSON(required)", "-o": "输出MIDI路径"}
executable: true
---

# Song Engineer — 歌曲工程聚合、诊断与优化

## 概述

本技能是「半成品聚合 + 持续优化编辑」闭环的中枢。它不替代现有的生成技能（ai_chords_master / muse-lyrics-gen / audio_chord_recognizer 等），而是**读半成品现状 → 诊断 → 给方向+教学 → 写回 song_engineer/ 产物目录**。现有 9 个技能是"做某个动作"，song_engineer 是"看到全局、做决策"。

**产物位置**：`workspace/project/{歌名}/song_engineer/`（独立产物目录，不改原始 `project.md` 雏形）。MD（人类可读）+ JSON（机器读写）双格式，多轨道拆分为 `track/` 下每轨一组 md+json。详见「工程目录约定」。
## 触发词

诊断工程、优化歌曲、看现状、下一步怎么改、继续打磨、工程体检、初始化工程、聚合半成品、工程初始化

## 核心能力

1. **初始化聚合**：把散落在各技能输出目录下的半成品产物（和弦方案 / lyrics / audio report / project.md 雏形）聚合进一个规范的工程MD
2. **现状诊断**：读 song_engineer 产物，输出完整性/一致性/对齐/风格契合度/优化空间五维诊断
3. **优化方向**：基于诊断结果，给出可操作的优化建议，优先调用现有生成技能
4. **知识教学**：诊断时关联 md/kb_repo/ 下已有知识，实现"AI辅助说明歌曲现状和优化方向，顺便教学一些知识"
5. **工程日志**：每次变更追加记录，形成可回溯迭代链

## 三种工作模式

### 模式 1：初始化模式（工程聚合）

**触发方式**：`初始化工程 {歌名}` 或 `聚合半成品`

**输入**：指定歌名 + 已存在的散件产物路径（或多个路径）
**输出**：`workspace/project/{歌名}/song_engineer/`（独立产物目录，不改 project.md）
```
song_engineer/
├── song_engineer.md      # 全局视图：基本信息+和弦/段落/歌词/诊断等全局内容（人类可读主视图）
├── song_engineer.json    # 上述内容的机器结构化版本（供前后端读写）
└── track/                # 分轨目录，每轨独立文件，支持单轨迭代
    ├── 01_吉他.md + 01_吉他.json
    ├── 02_主唱.md + 02_主唱.json
    ├── 03_lyrics.md + 03_lyrics.json
    └── 04_鼓组.md + 04_鼓组.json
    
```
**设计要点**：
- `project.md`（原始雏形）只读不改，song_engineer 产物完全独立在子目录，互不干扰
- MD 与 JSON 双格式：MD 人类可读主视图，JSON 机器结构化读写（为前后端工作台铺路）
- 多轨道文件化：每轨独立 md+json，单轨迭代不重写全局，不互相干扰

**流程**：
1. 确认目标工程目录 `workspace/project/{歌名}/` 存在，创建 `song_engineer/` 子目录
2. 扫描已有产物（只读）：
   - `workspace/ai_chords/{歌名}/` → 和弦方案
   - `workspace/muse_ai/{歌名}/` → 歌词
   - `workspace/audio_output/{歌名}/` → audio report
   - `workspace/project/{歌名}/project.md` → 已有雏形（如有）
   - `workspace/minimax_music_v3/{歌名}/` → minimax 产物（如有）
3. 按 [工程MD格式规范](../../../md/currdesign/工程MD格式规范.md) 的字段对照表，将各产物信息映射进对应区块
4. 处理重复字段：BPM/Capo/调号等优先取 ai_chords_master 的值（和弦方案是最权威的音高来源），如无则取 project.md 雏形或 lyrics
5. 全局内容写入 `song_engineer.md` + `song_engineer.json`；多轨道拆分为 `track/` 下每轨一组 md+json
6. 写工程日志：追加初始化记录（在 song_engineer.md 内）
7. 输出产物，告知用户哪些字段已聚合、哪些字段仍缺失（待后续补充）

**字段填充优先级**（当同一信息在多个来源出现时）：
| 字段 | 优先来源 |
|------|---------|
| BPM / 调号 / Capo / 编配调 / 实际音高 | ai_chords_master 和弦方案 |
| 和弦骨架 / 丰富化 / 把位 | ai_chords_master 和弦方案 |
| 旋律特征（音域/形态/能量） | audio_chord_recognizer |
| 歌词正文 | muse-lyrics-gen / muse_ai_master |
| 段落结构 | ai_chords_master（优先）或 project.md 雏形 |

### 模式 2：诊断模式（默认）

**触发方式**：`诊断工程 {歌名}` 或 `看现状` 或 `工程体检`

**输入**：`workspace/project/{歌名}/song_engineer/song_engineer.md`（如不存在则先跑初始化模式）
**输出**：更新 `song_engineer.md` 的「诊断与优化方向」区块 + `song_engineer.json` 的 diagnosis 字段 + 追加工程日志

**诊断维度**（详见 [diagnosis_dimensions.md](references/diagnosis_dimensions.md)）：

1. **完整性**：哪些段落/轨道/字段缺失？
   - 段落结构是否齐全？总和是否等于总小节数？
   - 多轨道规划是否建立？每个轨道是否有状态？
   - 歌词是否覆盖所有段落？段落标签是否与段落结构匹配？
   - 和弦详情是否同时有骨架和丰富化？
   - 基础设施（BPM/Capo/风格）是否填写？

2. **一致性**：跨文件的字段值是否矛盾？
   - song_engineer.md 的 BPM/调号/Capo 与和弦方案、lyrics 是否一致？
   - 段落结构的总小节数是否与和弦方案匹配？
   - 歌词段落标签（[Verse 1]/[Chorus]等）是否与段落结构表对齐？

3. **段落-和弦-歌词三者对齐**：
   - 段落结构表里的每个段落是否都有对应的和弦（在骨架/丰富化中出现）？
   - 歌词标签是否与段落结构表一一对应？
   - 小节数是否匹配？

4. **风格契合度**：对照 md/kb_repo/style/ 风格规范检查
   - 沙发小曲：有无鼓组？有无大横按和弦？有无高潮爆发？BPM 是否在 60-75？低音是否有半音下行？
   - 爱尔兰民谣：有无凯尔特调式特征？配器是否符合？
   - 禁用的乐器/元素是否出现在多轨道规划中？

5. **优化空间**：还有哪些地方可以做得更好？
   - 和弦丰富化：骨架是否已展开？利用了哪些色彩和弦？
   - 结构平衡：各段落音符密度/能量是否合理？
   - 歌词韵律：是否有明确的韵部设计？闭口音/开口音是否匹配风格？
   - 多轨完整性：还有哪些系填补的乐器/声部？

**诊断输出格式**：
```
### 现状诊断
#### 完整性 [▓▓▓▓░░░░] 60%
- 缺失：多轨道规划未建立（建议补充主唱/吉他/钢琴轨）
- 缺失：和弦时间线（可选，来自 audio report）
- 完整：段落结构、和弦骨架、歌词、旋律特征

#### 一致性
- ⚠️ 不一致：工程MD BPM=68，但 lyrics 全局设定 BPM=72
- ✅ 一致：Capo=3 与编配调=C/实际音高=Eb 匹配

#### 段落-和弦-歌词对齐
- ⚠️ lyrics 有 [Verse 1][Verse 2][Verse 3]，但段落结构表只有主歌A/主歌B/主歌A'
- ✅ 各段落小节数总和 = 36，与和弦方案一致

#### 风格契合度（对照：沙发小曲）
- ✅ 无鼓组 / 无爆发 / BPM=68 在 60-75 范围
- ✅ 低音有 C→B 半音下行
- ⚠️ 吉他编法建议提到"扫弦"，但沙发核规范建议扫弦仅限极轻空心扫

#### 优化空间
- [高] 和弦骨架仅 5 小节，可扩展完整段落循环
- [中] 歌词韵律：Verse 1 韵部 i/ü 统一，Verse 2 韵部 ei/ü/i 混用可优化
- [低] 可补充间奏的吉他旋律加花建议
```

### 模式 3：优化模式

**触发方式**：`优化 {歌名} 的 {方向}` 或 `继续打磨 {歌名}`

**输入**：`song_engineer/` 产物 + 优化方向（和弦/歌词/结构/某轨道）
**输出**：更新 `song_engineer.md` + 对应 `track/*.md+json` + 可能调用生成技能产出新文件

**流程**：
1. 先跑诊断模式（如近 24 小时内未诊断）
2. 根据用户指定的方向，调用对应生成技能：
   - 和弦优化 → 调用 `ai_chords_master` 技能
   - 歌词优化 → 调用 `muse-lyrics-gen` 技能
   - 结构优化 → 调用 `ai_chords_master` 技能（段落结构调整）
   - 轨道补充 → 直接编辑工程MD 的多轨道规划表
3. 将生成技能的新产出合并回 song_engineer 产物（按字段对照表）
4. 追加工程日志
5. 输出变更摘要

**合并规则**：
- 生成技能产出完整文件时，song_engineer 产物 内嵌核心信息+引用文件路径
- 不重复写已有内容，仅更新变化的字段
- 保留人工编辑的内容（日志中标记 `人工编辑` 的内容不覆盖，如确认覆盖则追加日志）

## 文件组织

```
.workbuddy/skills/song_engineer/
├── SKILL.md                          # 本文件
├── scripts/
│   ├── export_track_to_midi.py       # 分轨 JSON → MIDI（可播放）
│   └── synthesize_midi.py            # MIDI → WAV（极简 numpy 合成,可试听）
└── references/
    ├── diagnosis_dimensions.md       # 诊断维度细则
    ├── workflow.md                   # 三种模式的标准流程与合并规则
    └── engineer_format.md            # 工程MD格式速查（指向规范文档）
```

## 导出与试听

分轨数据(json)可直接转 MIDI 和 WAV 试听,验证数据准确性。

### 一键导出 MIDI

```bash
./.venv/python.exe .workbuddy/skills/song_engineer/scripts/export_track_to_midi.py \
  workspace/project/走在/song_engineer/track/01_吉他.json
# 自动选音色:吉他=program 25(钢弦吉他),主唱=program 0(钢琴)
# 输出:同目录 .mid 文件
```

支持两种数据源自动适配:
- `bars[].beats[]` 结构(吉他逐小节逐拍位)
- `melody_note_level.sections[].[]` 结构(主唱逐音符,beat_pos 形如 "5.1.1")

特殊处理:
- 泛音标记(名字带"泛音")按同音高处理
- "留白"/空音符跳过
- "末"字拍位(尾奏)推进到下一拍
- 中文 track_name 映射为英文(避免 mido latin-1 编码错误)

### 一键合成 WAV 试听

有两种合成后端,音质差异大:

**① FluidSynth + SoundFont(推荐,真实音质)**

```bash
./.venv/python.exe .workbuddy/skills/song_engineer/scripts/synthesize_midi_fs.py \
  workspace/project/走在/song_engineer/track/01_吉他.mid
# -> 01_吉他_fs.wav (真实 SoundFont 采样,钢弦吉他音色)
```
依赖 `.env` 配置:
```
fluidsynth_path=D:\...\fluidsynth-v2.5.7-win10-x64-cpp11\...
soundfonts_path=D:\...\sfs
```
sfs 目录需含 SoundFont(推荐 GeneralUser GS v1.471.sf2,32MB 轻量全乐器)。
pyfluidsynth + libfluidsynth-3.dll 已就绪,dll 路径自动从 .env 加到 PATH。

**② numpy 极简合成(无 SoundFont 时用)**

```bash
./.venv/python.exe .workbuddy/skills/song_engineer/scripts/synthesize_midi.py \
  workspace/project/走在/song_engineer/track/01_吉他.mid --timbre guitar
```

**音色选项**(numpy 版):
- `guitar`:钢弦吉他模拟(基频+3谐波+渐变包络)
- `piano`:钢琴模拟(基频+4谐波+快起慢衰)
- `vocal`:人声模拟(基频+共振峰 F1=800/F2=1200 + vibrato 5Hz + 气声白噪)
- `sine`:纯正弦波(测试用)

**重要限制**:numpy 版是极简合成,音质失真明显。**优先用 FluidSynth 版**,仅当无 SoundFont 时回退 numpy。

### 一键合成全曲(吉他+人声叠加)

```bash
# FluidSynth 版(推荐,真实音质)
./.venv/python.exe .workbuddy/skills/song_engineer/scripts/synth_full_song_fs.py
# -> full_song_fs.wav (3:06, 吉他 program=25 + 人声 program=85 Voice Oohs)

# numpy 版(无 SoundFont 时)
PYTHONUTF8=1 ./.venv/python.exe .workbuddy/skills/song_engineer/scripts/synth_full_song.py
# -> full_song.wav
```

**FluidSynth 全曲合成策略**:
- 吉他:program 25(钢弦吉他)SF 采样,vol=0.7
- 人声:program 85(Voice Oohs"喔"声,SF 无人声歌词,用合唱人声采样代替),vol=1.0
- 两轨 FluidSynth 分别渲染后叠加,归一化防削波
- 可调 `--guitar-program`/`--vocal-program`/`--guitar-vol`/`--vocal-vol`

**人声限制**:SoundFont 无人声歌词合成(那是 TTS/Vocaloid 范畴)。program 85 只能发"喔"声旋律,听不到具体歌词字。要真人声需用 Muse AI/MiniMax 在线生成。

### 端到端示例:导出吉他 MIDI 并合成 WAV
#### 说明
[gen_muisc.md](../../../md/kb_repo/info/gen_muisc.md)
[json_to_music.md](../../../md/kb_repo/info/json_to_music.md)
[FluidSynth.md](../../../md/kb_repo/info/FluidSynth.md)
#### 特别说明
无论numpy 还是 FluidSynth 都是粗糙塑料音色，比较适合做验证

#### 高保真成品
##### 难道人声生成
[hunman_gen.md](../../../md/kb_repo/info/hunman_gen.md)
##### 乐器音色
[track_up_level.md](../../../md/kb_repo/info/track_up_level/track_up_level.md)

#### 步骤
```bash
# 1. 导出 MIDI
PYTHONUTF8=1 ./.venv/python.exe .workbuddy/skills/song_engineer/scripts/export_track_to_midi.py \
  workspace/project/走在/song_engineer/track/01_吉他.json
# -> 01_吉他.mid (130 音符, BPM 68, 钢弦吉他音色)

# 2. 合成 WAV
PYTHONUTF8=1 ./.venv/python.exe .workbuddy/skills/song_engineer/scripts/synthesize_midi.py \
  workspace/project/走在/song_engineer/track/01_吉他.mid \
  -o workspace/project/走在/song_engineer/track/01_吉他.wav
# -> 01_吉他.wav (3:05, 约 8MB)

# 3. 全曲合成(吉他+人声)
PYTHONUTF8=1 ./.venv/python.exe .workbuddy/skills/song_engineer/scripts/synth_full_song.py
# -> full_song.wav (3:04, 约 8MB)
```

支持多个 set_tempo(精确处理 tempo 变化下的时间累积)。

## 工程目录约定

```
workspace/project/{歌名}/
├── project.md                        # 原始雏形（只读，song_engineer 不修改）
├── {歌名}.mp3                        # 生成出的成品音频（如有）
└── song_engineer/                    # ★ song_engineer 聚合产物（独立）
    ├── song_engineer.md              # 全局视图：基本信息+和弦/段落/歌词/旋律/日志/诊断（人类可读主视图）
    ├── song_engineer.json            # 上述内容的机器结构化版本（供前后端读写）
    └── track/                        # 分轨目录，每轨独立 md+json，支持单轨迭代
        ├── 01_吉他.md + 01_吉他.json      # 乐器轨
        ├── 02_主唱.md + 02_主唱.json      # 乐器轨
        ├── 03_lyrics.md + 03_lyrics.json  # 歌词轨（全歌词+段落对齐）
        └── 04_鼓组.md + 04_鼓组.json      # 乐器轨（可标"不需要"）
```

**轨道类型**：
- 乐器轨：吉他/主唱/鼓组等，含演奏规范、和弦指法、各段要点
- 歌词轨：全歌词按演唱顺序组织，每段标注对应段落名/小节/时长/和弦，与段落结构表对齐

**双格式约定**：
- `.md`：人类可读主视图，AI 与人直接阅读编辑
- `.json`：机器结构化版本，字段与 md 对齐，供前后端工作台程序读写（schema 字段标识版本）
- 两者必须保持同步：改 md 同时改 json，或以一方为准重新生成另一方

**多轨道文件化**：
- 每轨一组 `NN_乐器名.md` + `NN_乐器名.json`（NN 为两位序号）
- 单轨迭代只改对应文件，不重写全局
- 轨道状态：待录 / 草稿 / 定稿 / 不需要（不需要=显式记录禁用决策，避免诊断误报缺失）

## 与其他技能的协作

song_engineer 是中枢，其他技能是工具：

```
                          ┌─────────────────────┐
                          │   song_engineer     │
                          │  读现状/诊断/优化/   │
                          │  教学中枢（有状态）  │
                          └──────────┬──────────┘
                 读取现状 ◄───────────┼───────────► 写回 song_engineer/
                                     │ 调用
        ┌────────────────────────────┼────────────────────────────┐
        ▼                            ▼                            ▼
 ai_chords_master            muse-lyrics-gen            audio_chord_recognizer
 (和弦/段落/结构)             (歌词/韵律)                (扒谱/和弦识别/MIDI)
        │                            │                            │
        └────────────────────────────┼────────────────────────────┘
                                     ▼
              workspace/project/{歌名}/song_engineer/
              ★ 聚合产物（song_engineer.md + .json + track/）★
              （原始 project.md 雏形只读不动）
```

**关键区别**：
- 生成技能：输入->输出文件，一次调用一个任务，无状态
- song_engineer：读 song_engineer/ 产物现状 -> 分析 -> 决策 -> 调用生成技能 -> 合并回 song_engineer/ 产物，有状态，有记忆
- 原始 `project.md`：人工雏形，只读底座，song_engineer 从它读取但不写回

## 使用示例

```
用户: 初始化工程 走在
-> song_engineer 扫描全部散件（只读）
-> 按字段对照表聚合
-> 生成 song_engineer/ 产物：song_engineer.md+.json + track/ 每轨 md+json
-> 不改原始 project.md
-> 输出缺失字段清单

用户: 诊断工程 走在
-> song_engineer 读取 workspace/project/走在/song_engineer/song_engineer.md
-> 执行五维诊断
-> 更新 song_engineer.md 的「诊断与优化方向」区块 + song_engineer.json 的 diagnosis 字段
-> 追加工程日志
-> 输出诊断报告 + 优化建议

用户: 优化 走在 的和弦
-> song_engineer 先跑诊断（如需要）
-> 调用 ai_chords_master 丰富化
-> 合并结果回 song_engineer.md（和弦详情区块）+ 对应 track/01_吉他.md+json
-> 追加工程日志
-> 输出变更摘要
```

## 参考

- 工程MD格式规范：`md/currdesign/工程MD格式规范.md`
- 风格知识库：`md/kb_repo/style/`
- 歌词音律知识：`md/kb_repo/lyric/`
- 技能清单：`md/currdesign/skill.list.md`