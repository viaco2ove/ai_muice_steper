# 走在 · 沙发小曲 · 制作流程

> 歌曲：走在 | 风格：Lo-Fi 沙发小曲 | BPM 68 | Eb大调 | 3分04秒
> 本文档记录从雏形到半成品的完整制作流程，涵盖所有使用的技能、命令与产出文件。

---

## 一、项目概览

| 字段 | 值 |
|------|-----|
| 歌名 | 走在 |
| 风格 | 沙发小曲 / Lo-Fi |
| 情绪 | 慵懒内省，半成品，无爆发 |
| BPM | 68 |
| 调号 | Eb大调（Capo 3，C调指法）|
| 拍号 | 4/4 |
| 总小节 | 52 |
| 总时长 | 约 184 秒（3分04秒）|
| 人声音域 | G#3 ~ A4 |
| 禁用 | 鼓组、重贝斯、电音、副歌爆发 |

### 段落结构

```
前奏[4] → 主歌A[8] → 主歌B[8] → 间奏[4] → 副歌[8] → 主歌A'[8] → 副歌[8] → 尾奏[4]
0:00     0:14      0:42      1:11      1:25      1:53      2:21      2:49
```

### 和弦骨架

```
Cadd9 / C7sus4 → Em9/B / Em11/B → Cadd9 / C9
沙发下行进行：低音 C→B 半音下行
```

---

## 二、制作流程（7个阶段）

### 阶段 1 · 初始化与参考分析

**目标**：建立工程基础，分析参考音频，获取和弦与旋律素材。

#### 1.1 创建工程目录

```bash
# 创建项目目录
mkdir -p workspace/project/走在/
mkdir -p workspace/audio_output/走在/

# 复制参考音频（如有）
cp "标准录音3.mp3" workspace/audio_output/走在/
```

#### 1.2 音频分析与扒谱

使用 `audio_chord_recognizer` 技能对参考音频进行和弦识别与旋律提取：

```bash
# 触发技能
audio_chord_recognizer "C:\Users\viaco\Desktop\标准录音3.mp3"

# 实际执行（Python314）
cd D:\Users\viaco\PycharmProjects\ai_muice_steper
/c/Users/viaco/AppData/Local/Programs/Python/Python314/python.exe \
  .workbuddy/skills/audio_chord_recognizer/scripts/full_analysis.py \
  "workspace/audio_output/走在/标准录音3.wav" \
  -o workspace/audio_output/走在/
```

**产出**：
- `workspace/audio_output/走在/report.md` — 分析报告
- `workspace/audio_output/走在/tracks/` — 分轨音频（vocals/drums/bass/other.wav）
- `workspace/audio_output/走在/melody/pitch.csv` — 旋律音高数据
- `workspace/audio_output/走在/melody/melody.mid` — 旋律 MIDI
- `workspace/audio_output/走在/melody/vocals.mid` — 人声旋律 MIDI

**关键技术**：
- demucs v4 HTDemucs 分离音轨（vocals/drums/bass/other）
- librosa chroma 和弦识别
- pyin 旋律提取（MIDI 范围 A#2~G3）
- BPM 检测：~120（实际工程用 68）

---

### 阶段 2 · 和弦方案设计

**目标**：设计符合沙发小曲风格的和弦进行。

#### 2.1 初始化工程

```bash
# 触发 song_engineer 技能
初始化工程 走在
```

#### 2.2 生成和弦方案

使用 `ai_chords_master` 技能生成丰富化和弦方案：

```bash
# 在 Claude Code 中触发
ai_chords_master "走在" --style "沙发小曲" --bpm 68
```

**产出**：
- `workspace/project/走在/song_engineer/track/01_吉他.md` — 吉他轨完整设计
- 和弦骨架：`Cadd9 / C7sus4 → Em9/B / Em11/B`
- 丰富化指法：Cmaj9, C9, C13, Em9, Em11, E11

**设计要点**：
- 沙发下行进行：低音 C→B 半音下行
- 无大横按，开放/转位把位为主
- C7sus4 特殊音响（4音替代3音）：慵懒感

---

### 阶段 3 · 歌词创作

**目标**：创作符合沙发小曲气质的歌词。

#### 3.1 生成歌词

使用 `muse-lyrics-gen` 或 `muse-ai-master` 技能：

```bash
# 触发 muse-lyrics-gen
muse-lyrics-gen "走在" --style "沙发小曲慵懒内省" --bpm 68 --segments 8

# 或使用 minimax-music-web
```

**歌词核心规范**：
- 韵部：闭口音 i/ü/ei 为主（慵懒内收感）
- 情绪：无刻意起伏，副歌只比主歌多一点点气息支撑
- 唱法：气声40%+，真声为主，不用混声/嘶吼
- 咬字：自言自语感，松弛不发力

**产出**：
- `workspace/muse_ai/走在/lyrics/lyrics.md` — 完整歌词

#### 3.2 歌词音素转换

使用 `openutau_lyrics` 技能将歌词转换为 OpenUTAU 音素：

```bash
# 触发技能
openutau_lyrics "门虚掩着风掀了快递..." --output workspace/project/走在/song_engineer/track/02_主唱_phonemes.md
```

**产出**：
- `workspace/project/走在/song_engineer/track/02_主唱_phonemes.md` — CV 音素序列

---

### 阶段 4 · 旋律设计

**目标**：设计人声主旋律，结合参考曲扒谱与旋律写作规范。

#### 4.1 旋律参考分析

读取 `workspace/audio_output/走在/melody/pitch.csv` 提取旋律特征：
- 音域：A#2 ~ G3
- 特征：同音反复多，级进为主，整体下行趋势
- 参考曲风格：平缓叙事，无大跳

#### 4.2 旋律重写

使用 `melody_master` 技能，结合：
- 参考曲旋律特征（workspace/audio_output/走在/melody/vocals.mid）
- 旋律写作规范（md/kb_repo/info/主旋律/如何写出好听的主旋律.md）
- 转音设计规范（md/kb_repo/info/主旋律/转音设计.md）
- 现有旋律草稿（workspace/project/走在/song_engineer/track/02_主唱.md:34-40）

**设计原则**：
- 核心动机：G#3→A#3 上行级进
- 发展手法：同头换尾、模进、序列重复
- 副歌跳进：C4→D4，级进回填
- 整体趋势：下行为主
- 结构：起-承-转-合 四句体

**产出**：
- `workspace/project/走在/song_engineer/track/02_主唱.md` — 逐音符级旋律表（221音符）
- `workspace/project/走在/song_engineer/track/02_主唱.json` — 机器可读版本

---

### 阶段 5 · OpenUTAU 人声渲染

**目标**：将旋律转换为 OpenUTAU 可用的 .ustx 文件。

#### 5.1 导出 MIDI

```bash
cd D:\Users\viaco\PycharmProjects\ai_muice_steper
/.venv/python.exe .workbuddy/skills/song_engineer/scripts/export_track_to_midi.py \
  workspace/project/走在/song_engineer/track/02_主唱.json
```

**产出**：`workspace/project/走在/song_engineer/track/02_主唱.mid`

#### 5.2 生成 .ustx 文件

使用 `song_engineer` 的 `ustx_from_template.py` 脚本：

```bash
cd D:\Users\viaco\PycharmProjects\ai_muice_steper
/c/Users/viaco/AppData/Local/Programs/Python/Python314/python.exe \
  .workbuddy/skills/song_engineer/scripts/ustx_from_template.py \
  workspace/project/走在/song_engineer/track/02_主唱.md \
  workspace/project/走在/song_engineer/track/02_主唱-mid.ustx \
  workspace/project/走在/song_engineer/track/02_主唱.ustx
```

**关键技术**：
- 使用 Python314 + ruamel.yaml（兼容 YAML 1.2）
- 基于正确模板（02_主唱-mid.ustx）只替换 note 数据
- 字段名：singer / tone / position（非 singer_id / note_num / pos）
- ustx_version: "0.7"
- voice_parts 在根级

**产出**：
- `workspace/project/走在/song_engineer/track/02_主唱.ustx` — OpenUTAU 可直接打开
- `workspace/project/走在/song_engineer/ai-track/OpenUtau/02_主唱.ustx` — 同步副本

#### 5.3 OpenUTAU 内渲染

1. 打开 OpenUTAU
2. File → Open → 选择 `02_主唱.ustx`
3. 选择人声歌手（男声 Lo-Fi）
4. 调整 BREC/TENC/PITD 曲线（如需要）
5. Render → 导出 WAV

---

### 阶段 6 · 多轨道编曲

**目标**：生成完整的 13 轨多轨道工程。

#### 6.1 吉他轨系

| 轨道 | 内容 | 状态 |
|------|------|------|
| 01_吉他 | 基础分解和弦 | 定稿 |
| 05_solo吉他-主 | 间奏/副歌旋律 solo | 草稿 |
| 06_solo吉他-辅1 | 琶音辅助 | 草稿 |
| 07_solo吉他-辅2 | 布鲁斯色彩 | 草稿 |
| 08_节奏吉他 | 拍弦+勾弦 | 草稿 |

#### 6.2 人声轨系

| 轨道 | 内容 | 状态 |
|------|------|------|
| 02_主唱 | 人声主旋律 | 草稿 |
| 09_和声 | 三度和声 | 草稿 |
| 03_lyrics | 歌词轨 | 草稿 |

#### 6.3 环境音轨系

| 轨道 | 内容 | 状态 |
|------|------|------|
| 10_氛围垫音 | 合成器铺底 | 草稿 |
| 11_自然白噪音 | 雨/风声 | 草稿 |
| 12_泛音环境点缀 | 吉他泛音 | 草稿 |
| 13_轻贝斯 | 低频填充 | 草稿 |

#### 6.4 轨道渲染脚本

```bash
# 导出吉他 MIDI
/.venv/python.exe .workbuddy/skills/song_engineer/scripts/export_track_to_midi.py \
  workspace/project/走在/song_engineer/track/01_吉他.json

# FluidSynth 合成（需配置 .env）
/.venv/python.exe .workbuddy/skills/song_engineer/scripts/synth_full_song_fs.py
```

---

### 阶段 7 · AI 人声生成与成品

**目标**：生成高保真人声，混音输出成品。

#### 7.1 MiniMax Music AI 生成

使用 `minimax-music-api` 或 `minimax-music-web` 技能：

```bash
# 准备 prompt
# 编辑 workspace/project/走在/song_engineer/prompt_for_online_generator.md

# 使用 MiniMax Music 网页端
# 1. 打开 minimax-music-web
# 2. 粘贴 lyrics + minimax 控制标签
# 3. 选择男声 Lo-Fi 歌手
# 4. 生成
```

**MiniMax 控制标签示例**：
```
[沙发小曲慵懒内省，人声男低声呢喃，气声40%+，BPM68，Eb大调]
门虚掩着风掀了快递鞋尖沾雨...
```

#### 7.2 OpenUTAU + DiffSinger 本地渲染

1. 导入 02_主唱.ustx 到 OpenUTAU
2. 选择 DiffSinger 人声模型
3. 绘制 BREC/TENC/PITD 曲线
4. Render WAV

#### 7.3 混音

使用 DAW（Audacity/Premiere/FL Studio）：
1. 导入所有轨道 WAV
2. 吉他轨 vol=0.7
3. 人声轨 vol=1.0
4. 环境音轨 vol=0.3（ppp）
5. 混响 + EQ
6. 导出成品

**产出**：`workspace/project/走在/走在_no-watermark.mp3`

---

## 三、技能使用清单

| 序号 | 技能 | 用途 | 触发词 |
|------|------|------|--------|
| 1 | audio_chord_recognizer | 参考音频分析（和弦+旋律扒谱）| `audio_chord_recognizer "音频路径"` |
| 2 | ai_chords_master | 和弦方案设计与丰富化 | `ai_chords_master "歌名"` |
| 3 | muse-lyrics-gen | 歌词创作 | `muse-lyrics-gen "歌名"` |
| 4 | melody_master | 旋律设计与改编 | `melody_master` |
| 5 | openutau_lyrics | 歌词音素转换 | `openutau_lyrics` |
| 6 | song_engineer | 工程聚合与诊断 | `初始化工程 走在` / `诊断工程 走在` |
| 7 | minimax-music-api | AI 人声生成 | `minimax-music-api` |
| 8 | minimax-music-web | AI 人声网页生成 | `minimax-music-web` |

---

## 四、产出文件清单

### 核心工程文件

```
workspace/project/走在/
├── project.md                           # 原始雏形（只读）
├── 走在_no-watermark.mp3                # 成品音频
└── song_engineer/
    ├── song_engineer.md                  # 全局视图
    ├── song_engineer.json                # 机器结构化
    ├── prompt_for_online_generator.md    # AI生成 prompt
    └── track/
        ├── 01_吉他.md + .json + .mid + .wav
        ├── 02_主唱.md + .json + .mid + .ustx + .phonemes.md
        ├── 03_lyrics.md + .json
        ├── 04_鼓组.md + .json             # 不需要
        ├── 05_solo吉他-主.md + ...
        ├── 06_solo吉他-辅1.md + ...
        ├── 07_solo吉他-辅2.md + ...
        ├── 08_节奏吉他.md + ...
        ├── 09_和声.md + ...
        ├── 10_氛围垫音pad.md + ...
        ├── 11_自然白噪音.md + ...
        ├── 12_泛音环境点缀.md + ...
        └── 13_轻贝斯.md + ...
```

### 参考分析产出

```
workspace/audio_output/走在/
├── 标准录音3.wav                        # 源音频
├── report.md                            # 分析报告
├── chords.txt                           # 和弦时间线
├── melody/
│   ├── pitch.csv                        # 旋律音高数据
│   ├── melody.mid                       # 旋律 MIDI
│   └── vocals.mid                       # 人声旋律 MIDI
└── tracks/
    ├── vocals.wav                        # 人声
    ├── drums.wav                         # 鼓组
    ├── bass.wav                          # 贝斯
    └── other.wav                         # 其他
```

---

## 五、关键技术点

### 5.1 OpenUTAU .ustx 格式

- **ustx_version**: "0.7"
- **voice_parts**: 在根级（非 tracks[] 内）
- **字段名**: singer / tone / position（非 singer_id / note_num / pos）
- **Python 库**: 必须用 ruamel.yaml（pyyaml 不兼容 YAML 1.2）
- **Python 版本**: Python314（含 ruamel.yaml）

### 5.2 沙发小曲风格规范

- **BPM**: 60-75（本曲 68）
- **和弦进行**: 沙发下行 C7→Em7/B，低音半音下行
- **人声音域**: G#3 ~ A4（副歌上四度）
- **唱法**: 气声40%+，真声为主，轻声细语
- **禁用**: 鼓组、重贝斯、电音、副歌爆发

### 5.3 旋律写作规范

- **级进为主**: 1-2度为主，小跳（3-4度）点缀
- **避免大跳**: 5度以上跳进后必须级进回填
- **重复变化**: 动机重复、同头换尾、模进
- **副歌跳进**: C4→D4 真正推高，非停留在 A3

---

## 六、快捷命令汇总

```bash
# 1. 音频分析
cd D:\Users\viaco\PycharmProjects\ai_muice_steper
/c/Users/viaco/AppData/Local/Programs/Python/Python314/python.exe \
  .workbuddy/skills/audio_chord_recognizer/scripts/full_analysis.py \
  "workspace/audio_output/走在/标准录音3.wav" -o workspace/audio_output/走在/

# 2. 歌词转音素
/c/Users/viaco/AppData/Local/Programs/Python/Python314/python.exe \
  .workbuddy/skills/openutau_lyrics/scripts/lyrics_to_phonemes.py \
  -lyrics "门虚掩着..." -output workspace/project/走在/song_engineer/track/02_主唱_phonemes.md

# 3. 导出 MIDI
/.venv/python.exe .workbuddy/skills/song_engineer/scripts/export_track_to_midi.py \
  workspace/project/走在/song_engineer/track/02_主唱.json

# 4. 生成 .ustx（Python314 + ruamel.yaml）
/c/Users/viaco/AppData/Local/Programs/Python/Python314/python.exe \
  .workbuddy/skills/song_engineer/scripts/ustx_from_template.py \
  workspace/project/走在/song_engineer/track/02_主唱.md \
  workspace/project/走在/song_engineer/track/02_主唱-mid.ustx \
  workspace/project/走在/song_engineer/track/02_主唱.ustx

# 5. 全曲 FluidSynth 合成
/.venv/python.exe .workbuddy/skills/song_engineer/scripts/synth_full_song_fs.py
```

---

## 七、制作状态

| 阶段              | 状态 | 说明                                                           |
|-----------------|------|--------------------------------------------------------------|
| 阶段1 初始化与参考分析    | ✅ 完成 | audio_chord_recognizer 已产出 report + 分轨                       |
| 阶段2 和弦方案设计      | ✅ 完成 | ai_chords_master 已生成 01_吉他轨                                  |
| 阶段3 歌词创作        | ✅ 完成 | muse-lyrics-gen 已生成完整歌词                                      |
| 阶段4 旋律设计        | ✅ 完成 | melody_master 已重写 221 音符旋律 （MiniMaxmuisc->Melodyne 5->json和md） |
| 阶段5 OpenUTAU 渲染 | ✅ 完成 | 02_主唱.ustx 已生成（79.7KB）                                       |
| 阶段6 多轨道编曲       | 🟡 完成 | 吉他轨系完整，人声轨待 AI 生成                                            |
| 阶段7 AI人声与成品     | 🟡 完成 | MiniMax 生成半成品，OpenUTAU 待渲染                                   |
| 阶段8 AI人声与成品     | 🟡 完成 | OpenUTAU导出wav,合成多轨                                           |
| 阶段9 AI翻唱        | 🟡 完成 | MiniMax 翻唱，优化，然后再分轨                                          |

**下一步**：
1. 在 OpenUTAU 中打开 `02_主唱.ustx` 渲染人声.如果失败改为 加载mid 文件 再导入歌词试试。
2. 使用 MiniMax Music 生成高保真人声
3. DAW 混音输出成品
