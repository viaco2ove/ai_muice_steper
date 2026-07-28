# 技能清单

本文档罗列项目中所有技能，便于快速查找和使用。

---

## 目录

- [Muse AI 系列](#muse-ai-系列)
- [MiniMax Music 系列](#minimax-music-系列)
- [音频分析与处理](#音频分析与处理)
- [人声转 MIDI](#人声转-midi)
- [沙发小曲创作](#沙发小曲创作)
- [歌曲工程中枢](#歌曲工程中枢)

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
- `.workbuddy/skills/muse-lyrics-gen/references/lyric_prosody.md`

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
- `.workbuddy/skills/muse_ai_master/references/lyric_structure.md`
- `.workbuddy/skills/muse_ai_master/references/style_tags.md`
- `.workbuddy/skills/muse_ai_master/references/templates.md`

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
- `.workbuddy/skills/minimax-music-gen/references/prompt_guide.md`

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
- `.workbuddy/skills/minimax-music-api/references/control_tags.md`
- `.workbuddy/skills/minimax-music-api/references/prompt_guide.md`

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

**控制标签体系：**

| 维度 | 标签示例 |
|------|---------|
| 编曲 | `[吉他分解和弦]` `[钢琴轻柔铺底]` `[氛围垫音渐隐]` |
| 人声 | `[人声低输出呢喃]` `[气声极轻]` `[低声细语]` |
| 情绪 | `[平静慵懒]` `[迷茫疏离]` `[内敛克制]` |
| 禁用 | `[无鼓组]` `[禁止电音]` `[不爆发]` |

**参考文件：**
- `.workbuddy/skills/minimax-music-web/SKILL.md`
- `.workbuddy/skills/minimax-music-web/references/control_tags.md`

---

### minimax_music_v3

MiniMax Music 3 歌词格式化技能，将歌词从标准格式转换为网页端可识别的格式。

| 项目 | 内容 |
|------|------|
| **触发词** | 格式化歌词、MiniMax 歌词格式、转换歌词 |
| **输入** | `lyrics.md`（标准格式）或 `lyrics.design.md` |
| **输出** | `lyrics_*.txt` + `style_*.txt` |
| **输出目录** | `workspace/minimax_music_v3/` |

**工作流程：**

1. 读取歌词设计文件或标准歌词
2. 转换为 MiniMax Music 3 格式
3. 分离纯歌词和风格描述
4. 输出可粘贴到网页的文件

**核心发现：**

| 方案 | 说明 |
|------|------|
| 方案 A | 控制写在歌词内（`[编曲说明]` 方括号标签） |
| 方案 B（推荐） | 控制写在风格里，歌词保持干净 |

**参考文件：**
- `.workbuddy/skills/minimax_music_v3/SKILL.md`
- `.workbuddy/skills/minimax_music_v3/references/control_tags.md`

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
- `.workbuddy/skills/audio_chord_recognizer/references/usage_guide.md`

---

## 人声转 MIDI

### wav_mid_human

人声 WAV 转可听旋律 MIDI 技能，专门解决 `audio_chord_recognizer` 产出的 MIDI 碎音问题。支持双后端：basic_pitch 神经网络（优先，贴合人声轮廓）+ pyin 8步清洗（fallback）。

| 项目 | 内容 |
|------|------|
| **触发词** | 人声转MIDI、wav转mid、旋律线MIDI、干净MIDI、清洗碎音、听出旋律、hum to midi |
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

**实测效果**（vocals.wav）：音符数 196->29，碎音率 57.1%->0.0%，平均时长 0.084s->0.524s

**核心脚本：**

| 脚本 | 功能 |
|------|------|
| `wav_to_midi_bp.py` | **推荐** basic_pitch神经网络后端，贴合人声轮廓+velocity |
| `wav_to_midi.py` | pyin后端，8步清洗管线（fallback） |
| `merge_vocal_notes.py` | **连贯性后处理**：修正basic_pitch把长音抖碎成幻音的问题 |
| `compare_quality.py` | 对比新旧MIDI质量，生成quality_report.md |

**参考文件：**
- `.workbuddy/skills/wav_mid_human/SKILL.md`
- `.workbuddy/skills/wav_mid_human/references/wav_to_mid_principles.md`（清洗原理）
- `.workbuddy/skills/wav_mid_human/references/usage_examples.md`（使用场景）
- `md/kb_repo/info/wav_to_mid.md`（问题根源知识库）

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

**基础信息记录：**

| 字段 | 说明 | 示例 |
|------|------|------|
| capo | 夹几品 | 3（三品） |
| capo_key | 编配在哪个调 | C（C大调） |
| actual_key | 实际弹出的调（自动计算） | Eb |

**和弦丰富化方向：**

| 方向 | 候选和弦 | 效果 |
|------|---------|------|
| 色彩注入 | Cmaj9、Cadd9、C9、C13、C7sus4 | 更柔和的主调氛围 |
| 转位优化 | Em11/B、C7/E | 低音线条更流动 |
| 挂留和弦 | C7sus4、Em7sus4 | 减速感 |
| 爵士色彩 | Cmaj7、Em11、Bm9 | 更迷蒙的过渡 |

**禁止事项：**

- 不使用大横按强力和弦
- 不加入增和弦或减七和弦
- 不使用快速 II-V-I 进行
- 延伸形态中不使用失真音色、强鼓点

**参考文件：**
- `.workbuddy/skills/ai_chords_master/SKILL.md`
- `.workbuddy/skills/ai_chords_master/references/沙发小曲_丰富化编曲方案_慵懒版.md`

---

## 歌曲工程中枢

### song_engineer

歌曲工程聚合、诊断与优化技能，是「半成品聚合 + 持续优化编辑」闭环的中枢。读半成品现状 -> 诊断 -> 给方向+教学 -> 直接改工程MD。不替代生成技能，而是聚合+闭环。

| 项目 | 内容 |
|------|------|
| **触发词** | 诊断工程、优化歌曲、看现状、下一步怎么改、继续打磨、工程体检、初始化工程、聚合半成品 |
| **输入** | `workspace/project/{歌名}/project.md` 或散件产物 |
| **输出** | 更新 `project.md`（诊断区块 + 工程日志） |
| **工作目录** | `workspace/project/{歌_name}/` |

**三种工作模式：**

| 模式 | 说明 |
|------|------|
| 初始化模式 | 扫描散件（和弦方案/lyrics/audio report）-> 按字段对照表聚合进规范工程MD |
| 诊断模式（默认） | 读工程MD -> 五维诊断（完整性/一致性/对齐/风格契合度/优化空间）-> 写入诊断区块 |
| 优化模式 | 按方向调用生成技能（ai_chords/muse-lyrics等）-> 合并结果回工程MD -> 追加日志 |

**五维诊断：**

| 维度 | 检查内容 |
|------|---------|
| 完整性 | 段落/轨道/字段是否齐全，给出完成度百分比 |
| 一致性 | BPM/调号/Capo 跨文件是否矛盾 |
| 段落-和弦-歌词对齐 | 三者对应关系是否匹配 |
| 风格契合度 | 对照 kb_repo/style/ 风格规范检查（如沙发小曲禁鼓组） |
| 优化空间 | 和弦丰富化/结构平衡/歌词韵律/多轨完整性 |

**关键区别：**
- 生成技能（其余9个）：输入->输出文件，一次一个任务，无状态
- song_engineer：读工程MD现状->分析->决策->调用生成技能->合并回工程MD，有状态、有迭代记忆

**参考文件：**
- `.workbuddy/skills/song_engineer/SKILL.md`
- `.workbuddy/skills/song_engineer/scripts/export_track_to_midi.py`（分轨 JSON -> MIDI）
- `.workbuddy/skills/song_engineer/scripts/synthesize_midi_fs.py`（FluidSynth+SoundFont 真实合成，推荐）
- `.workbuddy/skills/song_engineer/scripts/synthesize_midi.py`（numpy 极简合成，无 SoundFont 时 fallback）
- `.workbuddy/skills/song_engineer/scripts/synth_full_song_fs.py`（FluidSynth 合成全曲，推荐）
- `.workbuddy/skills/song_engineer/scripts/synth_full_song.py`（numpy 合成全曲，fallback）
- `.workbuddy/skills/song_engineer/references/diagnosis_dimensions.md`
- `.workbuddy/skills/song_engineer/references/workflow.md`
- `.workbuddy/skills/song_engineer/references/engineer_format.md`
- `md/currdesign/工程MD格式规范.md`（工程MD格式契约）

---

## 技能协作关系

以 `song_engineer` 为中枢的迭代闭环（其余生成技能是工具）：

```
                          ┌─────────────────────┐
                          │   song_engineer     │
                          │  读现状/诊断/优化/   │
                          │  教学中枢（有状态）  │
                          └──────────┬──────────┘
                 读取现状 ◄───────────┼───────────► 写回工程
                                     │ 调用
        ┌────────────────────────────┼────────────────────────────┐
        ▼                            ▼                            ▼
 ai_chords_master            muse-lyrics-gen            audio_chord_recognizer
 (和弦/段落/结构)             (歌词/韵律)                (扒谱/和弦识别/MIDI)
        │                            │                            │
        └────────────────────────────┼────────────────────────────┘
                                     ▼
                          workspace/project/{歌名}/project.md
                          ★ 工程MD = 唯一真相源 ★
                                     │
                          ┌──────────┴──────────┐
                          ▼                     ▼
                   minimax_music_v3        muse_ai_master
                   (格式化->生成)          (歌词结构->生成)
                                     │
                                     ▼
                              成品音频 (mp3)
```

**单向流水线（生成阶段，从0到半成品）：**
```
哼唱 ──audio_chord_recognizer──▶ 和弦/旋律 ──ai_chords_master──▶ 和弦方案+段落
                                                                      │
              muse-lyrics-gen ◄──和弦骨架────────────────────────────┘
                    │
                    ▼ lyrics.md ──minimax_music_v3──▶ 歌词.txt+风格.txt ──▶ MiniMax生成
```

**迭代闭环（优化阶段，从半成品持续优化到成品，song_engineer 主导）：**
```
project.md 现状 ──诊断──▶ 五维报告+优化建议+知识点 ──决策──▶ 调用生成技能
     ▲                                                    │
     └────────────── 合并回工程MD + 工程日志 ◄────────────┘
     （持续循环：看现状->给方向->改->再看->再改）
```

**关键：** 生成技能之间靠文件传递（单向流水线）；song_engineer 靠读写工程MD形成闭环（有状态迭代）。两者互补：流水线负责"从0到半成品"，闭环负责"从半成品持续优化到成品"。

---

## 快速参考表

| 需求 | 推荐技能 |
|------|---------|
| 聚合散件半成品为统一工程 | `song_engineer`（初始化模式） |
| 诊断歌曲工程现状/下一步怎么改 | `song_engineer`（诊断模式） |
| 持续优化打磨半成品 | `song_engineer`（优化模式） |
| 分轨导出 MIDI 并合成 WAV 试听 | `song_engineer` scripts(export_track_to_midi + synthesize_midi) |
| 合成全曲 wav(吉他+人声叠加) | `song_engineer` scripts(synth_full_song) |
| 根据歌词设计规范生成歌词 | `muse-lyrics-gen` |
| 用 Muse AI 生成歌曲 | `muse_ai_master` |
| MiniMax Music 3 网页端生成 | `minimax-music-web` + `minimax_music_v3` |
| mmx CLI 命令行生成 | `minimax-music-gen` |
| API 编程集成 | `minimax-music-api` |
| 从音频识别和弦/旋律 | `audio_chord_recognizer` |
| 人声转可听旋律MIDI（清洗碎音） | `wav_mid_human` |
| 设计沙发小曲和弦编曲 | `ai_chords_master` |
