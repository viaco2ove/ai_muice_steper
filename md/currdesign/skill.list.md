# 技能清单

本文档罗列项目中所有技能，便于快速查找和使用。

---

## 目录

- [Muse AI 系列](#muse-ai-系列)
- [MiniMax Music 系列](#minimax-music-系列)
- [音频分析与处理](#音频分析与处理)
- [人声转 MIDI](#人声转-midi)
- [沙发小曲创作](#沙发小曲创作)
- [歌词与音素](#歌词与音素)
- [旋律设计](#旋律设计)
- [歌曲工程中枢](#歌曲工程中枢)
- [工具类](#工具类)
- [技能协作关系](#技能协作关系)

---

## Muse AI 系列

### muse-lyrics-gen

歌词生成技能，基于歌词设计规范（`lyrics.design.md`）生成符合 Lo-Fi 沙发小曲韵律规则的歌词。

| 项目 | 内容 |
|------|------|
| **触发词** | 生成歌词、写歌词、根据 design 写歌词 |
| **输入** | `lyrics/lyrics.design.md` |
| **输出** | `lyrics/lyrics.md` |
| **核心规则** | 8拍/组结构、闭口音韵脚（i/ü/ei）、情绪间接表达、留白控制 |

**韵律规则：**

| 规则 | 要求 |
|------|------|
| 行长度 | 3-6 字 |
| 每组结构 | C 和弦行 3-4 音节，Em/B 和弦行 4-5 音节 |
| 韵脚位置 | 每组第 2 行末尾押韵 |
| 韵部 | i/ü/ei（闭口音） |
| 情绪 | 间接表达，用细节替代情绪词 |

**参考文件：**
- `.workbuddy/skills/muse-lyrics-gen/SKILL.md`

---

### muse_ai_master

Muse AI 大师模式歌词创作技能，包含完整的歌词结构标签、格式规范、风格推荐和示例模板。

| 项目 | 内容 |
|------|------|
| **触发词** | Muse AI、大师模式、创建歌词、段落结构 |
| **输入** | 歌曲主题、风格定位 |
| **输出** | `workspace/muse_ai/{song_name}/` |

**工作模式：**

| 模式 | 说明 |
|------|------|
| 编曲模式（默认） | 需要【全局设定】区块，包含曲风/BPM/人声/配器/禁用项/和弦骨架 |
| 段落模式 | 只需风格标签和语种/情绪标签，不写【全局设定】 |

**标签系统：**

| 类型 | 标签示例 |
|------|---------|
| 结构标签 | `[Intro]`、`[Verse]`、`[Chorus]`、`[Bridge]` |
| 人声标签 | `[Male Vocal]`、`[Whisper]`、`[Harmony]` |
| 风格标签 | `[a cappella]`、`[dolce]`、`[legato]`、`[piano]` |
| 语种标签 | `[普通话]`、`[粤语]`、`[English]` |

**参考文件：**
- `.workbuddy/skills/muse_ai_master/SKILL.md`

---

## MiniMax Music 系列

### minimax-music-gen

mmx CLI 入口技能，用于通过 mmx 命令行工具生成音乐。

| 项目 | 内容 |
|------|------|
| **触发词** | mmx 音乐、mmx 生成、minimax CLI |
| **接口** | mmx CLI |
| **歌词格式** | `[verse]` `[chorus]` 英文标签 |

**参考文件：**
- `.workbuddy/skills/minimax-music-gen/SKILL.md`

---

### minimax-music-api

MiniMax API 编程调用技能，用于程序化集成和批量生成。

| 项目 | 内容 |
|------|------|
| **触发词** | API、集成开发、batch 批量、编程调用 |
| **接口** | MiniMax API / mmx CLI |
| **歌词格式** | `[verse]` `[chorus]` 英文标签 |
| **控制方式** | 命令行参数 |

**控制参数：**

| 参数 | 说明 |
|------|------|
| `--vocals` | 人声类型 |
| `--mood` | 情绪氛围 |
| `--genre` | 音乐流派 |
| `--instruments` | 乐器指定 |
| `--avoid` | 禁用元素 |

**参考文件：**
- `.workbuddy/skills/minimax-music-api/SKILL.md`

---

### minimax-music-web

MiniMax Music 3 网页端技能，用于手动粘贴歌词和风格描述到网页生成音乐。

| 项目 | 内容 |
|------|------|
| **触发词** | 网页端、MiniMax Music 3、粘贴生成 |
| **接口** | https://www.minimaxi.com/audio/music |
| **歌词格式** | `[Verse]` `[Chorus]` 中文标签 + `[...]` 方括号编曲说明 |
| **控制方式** | 歌词内嵌段落控制 + 风格描述 |

**歌词格式规范：**

| 元素 | 格式 |
|------|------|
| 结构标签 | `[Intro]`、`[Verse]`、`[Chorus]` 等（首字母大写） |
| 编曲说明 | `[吉他分解和弦轻柔开场]` 方括号包裹，放在标签后第一行 |
| 歌词行 | 每行一句，空行分隔段落 |
| 气声/呢喃 | `…嗯…` 用省略号 |

**参考文件：**
- `.workbuddy/skills/minimax-music-web/SKILL.md`

---

### minimax_music_v3

MiniMax Music 3 歌词格式化技能，将歌词从标准格式转换为网页端可识别的格式。

| 项目 | 内容 |
|------|------|
| **触发词** | 格式化歌词、MiniMax 歌词格式、转换歌词 |
| **输入** | `lyrics.md`（标准格式）或 `lyrics.design.md` |
| **输出** | `lyrics_*.txt` + `style_*.txt` |
| **输出目录** | `workspace/minimax_music_v3/` |

**参考文件：**
- `.workbuddy/skills/minimax_music_v3/SKILL.md`

---

## 音频分析与处理

### audio_chord_recognizer

纯本地 Python 音频分析工具集，零在线 API 依赖。

| 项目 | 内容 |
|------|------|
| **触发词** | 识别和弦、音频分析、和弦识别、旋律识别、扒谱、分离音轨、人声分离、音频转MIDI |
| **输出目录** | `workspace/audio_output/{song_name}/` |

**核心脚本：**

| 脚本 | 功能 |
|------|------|
| `separate_tracks.py` | 使用 demucs 分离人声/鼓/贝斯/其他 |
| `recognize_chords.py` | 基于 librosa chroma 特征识别和弦进行 |
| `recognize_melody.py` | 提取旋律并生成 MIDI |
| `full_analysis.py` | 一键全流程：分离 → 和弦 → 旋律 → report.md |

**技术栈：**

- 和弦识别：librosa chroma_cqt → 余弦相似度匹配
- 旋律识别：librosa.pyin 基频追踪 + basic-pitch MIDI 生成
- 音轨分离：demucs v4（HTDemucs）
- 环境：Python 3.11，torch CPU 版，无需显卡

**参考文件：**
- `.workbuddy/skills/audio_chord_recognizer/SKILL.md`

---

## 人声转 MIDI

### wav_mid_human

人声 WAV 转可听旋律 MIDI 技能，专门解决碎音问题。支持双后端：basic_pitch 神经网络（优先）+ pyin 8步清洗（fallback）。

| 项目 | 内容 |
|------|------|
| **触发词** | 人声转MIDI、wav转mid、旋律线MIDI、干净MIDI、清洗碎音、hum to midi |
| **输入** | 人声干声 WAV（带伴奏需先分轨取 vocals） |
| **输出目录** | `melody_basicpitch/`（推荐）或 `melody_human/`（pyin后端）|
| **依赖** | 项目 `.venv`（basic_pitch+onnxruntime / librosa / soundfile / mido）|

**与 audio_chord_recognizer 的区别：**

| 维度 | recognize_melody.py | wav_mid_human |
|------|---------------------|---------------|
| 碎音率 | ~57% | <5% |
| 最小音符时长 | 无过滤 | 80ms（可配） |
| 中值滤波/跳变修正/音域过滤 | 无 | 有 |
| 用途 | 粗略音高分析 | 可听旋律线、导入DAW |

**8 步清洗管线：** 加载 -> 预处理(noise gate) -> pyin提取 -> 有声帧过滤 -> 中值滤波 -> 跳变修正 -> 音符合并 -> 碎音过滤

**参考文件：**
- `.workbuddy/skills/wav_mid_human/SKILL.md`

---

## 沙发小曲创作

### ai_chords_master

沙发小曲编曲与创作技能，基于用户给定的和弦和哼唱旋律生成丰富化编曲方案。

| 项目 | 内容 |
|------|------|
| **触发词** | 写和弦、和弦进行、沙发小曲、沙发进行、丰富和弦、编曲、设计段落、和弦走向 |
| **输入** | 基础和弦 + 哼唱旋律（可选） |
| **输出目录** | `workspace/ai_chords/{song_name}/` |

**核心功能：**

1. 丰富化和弦进行（叠加色彩和弦、转位、延伸音）
2. 段落结构设计（完整的前奏/主歌/副歌/间奏/尾奏规划）
3. 旋律构思（基于识别到的旋律音给出走向建议）

**禁止事项：**

- 不使用大横按强力和弦
- 不加入增和弦或减七和弦
- 不使用快速 II-V-I 进行
- 延伸形态中不使用失真音色、强鼓点

**参考文件：**
- `.workbuddy/skills/ai_chords_master/SKILL.md`

---

## 歌词与音素

### openutau_lyrics

将中文歌词转换为 OpenUTAU 可唱的音素序列（CV Phonemes）。

| 项目 | 内容 |
|------|------|
| **触发词** | 歌词音素、音素设计、openutau lyrics、拼音转音素、中文歌词转音素、ustx 歌词编辑、生成 openutau 歌词 |
| **输入** | `track/02_主唱.md`（旋律设计文档）|
| **输出** | `ai-track/02_主唱_lyrics.txt`（每行一个音节）|

**音素类型：**

| 类型 | 格式 | 示例 |
|------|------|------|
| CV Phonemes | 声母+韵母 | `门=m+en` |
| VC Phonemes | 韵母+声母 | `门=en+m` |
| 纯汉字 | 直接汉字 | `门`（音素器自动转换）|

**OpenUTAU 导入流程：**

1. 用生成的 `.mid` 文件在 OpenUTAU 新建音轨
2. 导入 `.txt` 歌词文件（每行对应一个音符）
3. 选择音色库
4. 渲染人声

**参考文件：**
- `.workbuddy/skills/openutau_lyrics/SKILL.md`

---

## 旋律设计

### melody_master

旋律设计与改编技能，基于参考曲扒谱 + 旋律写作规范 + 转音设计，重写/优化人声主旋律。

| 项目 | 内容 |
|------|------|
| **触发词** | 旋律设计、主旋律改编、分析旋律、写主旋律 |
| **输入** | 参考曲 pitch.csv / `track/02_主唱.md` |
| **输出** | `track/02_主唱.md`（更新后的旋律设计）|

**旋律写作黄金规则：**

| 维度 | 规则 |
|------|------|
| 音域控制 | 舒适区间：C3 ~ F4 |
| 音高走向 | 温柔抒情下行为主，副歌高潮上行回落 |
| 节奏搭配 | 长短音结合，重拍放高音长音 |
| 发展手法 | 起-承-转-合四句体，动机重复/模进 |

**参考文件：**
- `.workbuddy/skills/melody_master/SKILL.md`
- `md/kb_repo/info/主旋律/如何写出好听的主旋律.md`

---

## 歌曲工程中枢

### song_engineer

歌曲工程聚合、诊断与优化技能，是「半成品聚合 + 持续优化编辑」闭环的中枢。

| 项目 | 内容 |
|------|------|
| **触发词** | 诊断工程、优化歌曲、看现状、下一步怎么改、继续打磨、工程体检、初始化工程、聚合半成品 |
| **输入** | `workspace/project/{歌名}/project.md` 或散件产物 |
| **输出** | 更新 `project.md`（诊断区块 + 工程日志）|
| **工作目录** | `workspace/project/{歌名}/` |

**三种工作模式：**

| 模式 | 说明 |
|------|------|
| 初始化模式 | 扫描散件 -> 聚合进规范工程MD |
| 诊断模式（默认） | 五维诊断 -> 写入诊断区块 |
| 优化模式 | 调用生成技能 -> 合并回工程MD |

**五维诊断：**

| 维度 | 检查内容 |
|------|---------|
| 完整性 | 段落/轨道/字段是否齐全 |
| 一致性 | BPM/调号/Capo 跨文件是否矛盾 |
| 段落-和弦-歌词对齐 | 三者对应关系是否匹配 |
| 风格契合度 | 对照风格规范检查 |
| 优化空间 | 和弦丰富化/结构平衡/多轨完整性 |

**关键区别：**
- 生成技能：输入->输出文件，一次一个任务，无状态
- song_engineer：有状态、有迭代记忆，读现状->分析->决策->调用技能->写回工程

**参考文件：**
- `.workbuddy/skills/song_engineer/SKILL.md`
- `md/currdesign/工程MD格式规范.md`

---

### remix-master

配置驱动混音技能，读 `remix.json` 配置每条音轨的音量/增益/静音/声像，混合成最终母带。

| 项目 | 内容 |
|------|------|
| **触发词** | 混音、remix、放大主唱、调音量、音轨平衡、母带、调音 |
| **输入** | `track/*.wav`（真实干声）+ `*.mid` + `remix.json` |
| **输出** | `track/full_remix.wav` |

**核心字段：**

| 字段 | 作用 |
|------|------|
| `source` | 音源类型：`auto` / `wav` / `midi` |
| `vol` | 线性音量倍率（0.0~2.0） |
| `gain_db` | 分贝增益 |
| `mute` | 静音该轨 |
| `pan` | 声像（-1左 ~ +1右） |

**参考文件：**
- `.workbuddy/skills/remix-master/SKILL.md`

---

### musescore-cooperate

与 MuseScore 协作生成/读取多轨 `.mscx` 乐谱文件。

| 项目 | 内容 |
|------|------|
| **触发词** | MuseScore、mscx、乐谱、多轨总谱、乐谱导出、打谱 |
| **输入** | `track/*.json` / `*.mid` |
| **输出** | `track/musescore/*.mscx` |

**工作流：**
1. `mscx_generator.py` → 生成全部分轨 .mscx + 多轨总谱
2. MuseScore Studio 打开 → 精细编辑
3. `mscx_reader.py` → 读取编辑后的乐谱数据回工程

**参考文件：**
- `.workbuddy/skills/musescore-cooperate/SKILL.md`

---

## 工具类

### ftp-download

FTP/FTPS 文件下载工具，支持递归目录下载、断点续传、同步模式。

| 项目 | 内容 |
|------|------|
| **触发词** | FTP下载、FTPS、递归FTP、FTP同步、FTP续传、从FTP获取文件 |
| **接口** | Python 标准库（ftplib, argparse） |
| **零依赖** | 仅使用 Python 标准库，无需安装额外包 |

**参考文件：**
- `.workbuddy/skills/ftp-download/SKILL.md`

---

## 技能协作关系

### 单向流水线（生成阶段，从0到半成品）

```
哼唱 ──audio_chord_recognizer──▶ 和弦/旋律
                                      │
         ai_chords_master ◄──────────┘
              │
muse-lyrics-gen ◄── 和弦骨架
              │
              ▼ lyrics.md ──minimax_music_v3──▶ MiniMax生成
```

### 迭代闭环（优化阶段，song_engineer 主导）

```
project.md 现状 ──诊断──▶ 五维报告+优化建议
     ▲                              │
     │                         调用生成技能
     │                              │
     └──────── 合并回工程MD + 日志 ◄─┘
```

### 协作图

```
                    ┌─────────────────────┐
                    │   song_engineer     │
                    │  诊断/优化/教学中枢  │
                    └──────────┬──────────┘
                               │ 调用
     ┌─────────────────────────┼─────────────────────────┐
     ▼                         ▼                         ▼
ai_chords_master        muse-lyrics-gen          audio_chord_recognizer
  (和弦/段落)              (歌词/韵律)              (扒谱/分离)
     │                         │                         │
     └─────────────────────────┼─────────────────────────┘
                               ▼
              workspace/project/{歌名}/project.md
              ★ 工程MD = 唯一真相源 ★
```

---

## 快速参考表

| 需求 | 推荐技能 |
|------|---------|
| 聚合散件半成品为统一工程 | `song_engineer`（初始化模式） |
| 诊断歌曲工程现状/下一步怎么改 | `song_engineer`（诊断模式） |
| 持续优化打磨半成品 | `song_engineer`（优化模式） |
| 生成 OpenUTAU 可用人声歌词 | `openutau_lyrics` |
| 旋律设计与改编 | `melody_master` |
| 根据歌词设计规范生成歌词 | `muse-lyrics-gen` |
| 用 Muse AI 生成歌曲 | `muse_ai_master` |
| MiniMax 网页端生成 | `minimax-music-web` + `minimax_music_v3` |
| mmx CLI 命令行生成 | `minimax-music-gen` |
| API 编程集成 | `minimax-music-api` |
| 从音频识别和弦/旋律 | `audio_chord_recognizer` |
| 人声转可听旋律MIDI | `wav_mid_human` |
| 设计沙发小曲和弦编曲 | `ai_chords_master` |
| 混音/母带 | `remix-master` |
| MuseScore 乐谱协作 | `musescore-cooperate` |
| FTP 文件下载 | `ftp-download` |
