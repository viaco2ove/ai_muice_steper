---
name: musescore-cooperate
description: >
  与 MuseScore 协作：生成 .mscx 乐谱文件、读取 .mscx 提取音符/歌词/调号/速度，在 MuseScore 中编辑后导回工程。
  触发词：MuseScore、mscx、乐谱、多轨总谱、乐谱导出、打谱
agent_created: true
---

# MuseScore Cooperate — 与 MuseScore 协作技能

## 解决什么问题

用 AI 生成的多轨 MIDI 在 MuseScore 里打开做进一步编辑（修正音符、添加歌词、调整排版），编辑后再导出为 JSON/MID 回到工程闭环。

MuseScore `.mscx` 是纯 XML 文本格式，可以：
- **生成**：从 `track/*.json` 或 `*.mid` 生成 MuseScore 可打开的多轨乐谱
- **读取**：解析 `.mscx` 提取音符、歌词、调号、BPM
- **协同**：在 MuseScore 里精细编辑后，用 `mscx_reader.py` 导回工程数据

## 触发词

MuseScore、mscx、乐谱、多轨总谱、乐谱导出、打谱、和 MuseScore 协作、打开乐谱、生成乐谱

## 核心文件

```
.workbuddy/skills/musescore-cooperate/
├── SKILL.md                    # 本文件
└── scripts/
    ├── mscx_generator.py       # 从 JSON/MID 生成 .mscx
    └── mscx_reader.py          # 读取 .mscx 提取数据
```

## 用法

### 1. 生成 MuseScore 乐谱

```bash
# 生成全部轨道的单轨乐谱 + 多轨总谱
./.venv/python.exe .workbuddy/skills/musescore-cooperate/scripts/mscx_generator.py \
    --project 走在 --full

# 只生成吉他和主唱
./.venv/python.exe .workbuddy/skills/musescore-cooperate/scripts/mscx_generator.py \
    --project 走在 --tracks "01_吉他,02_主唱"

# 指定输出目录
./.venv/python.exe .workbuddy/skills/musescore-cooperate/scripts/mscx_generator.py \
    --project 走在 -o /path/to/musescore
```

输出：
```
workspace/project/{歌名}/song_engineer/track/musescore/
├── 01_吉他.mscx
├── 02_主唱.mscx
├── 05_solo吉他主.mscx
├── ...
└── full_score.mscx   ← 多轨总谱，用 MuseScore 打开
```

用 **MuseScore Studio** 打开 `.mscx` 文件即可查看/编辑。

### 2. 在 MuseScore 中编辑

推荐工作流：
1. 打开 `full_score.mscx`（多轨总谱）→ 查看全部轨道
2. 打开单轨 `.mscx` → 精细编辑（修正音符、添加歌词、调整力度）
3. 保存 `.mscx`（MuseScore 会保留 XML 编辑内容）

**MuseScore 中常用操作：**
- 添加歌词：选中音符 → `Ctrl+L` → 输入歌词
- 调整力度：`Shift+E` → 拖动或输入数值
- 修正音符：直接拖动琴键或删除重输
- 导出音频：菜单 → 文件 → 导出 → WAV/MP3

### 3. 从 .mscx 读取数据回工程

```bash
# 读取单轨乐谱信息
python mscx_reader.py workspace/project/走在/song_engineer/track/musescore/02_主唱.mscx

# 导出为 JSON
python mscx_reader.py 02_主唱.mscx -o 02_主唱_from_ms.json

# 对比两个 mscx 的差异
python mscx_reader.py a.mscx b.mscx --diff
```

### 4. 读取信息字段

| 字段 | 说明 |
|------|------|
| `title` | 乐谱标题 |
| `bpm` | 速度（BPM） |
| `time_sig` | 拍号（如 4/4） |
| `key_sig` | 调号（正数=升号数，负数=降号数） |
| `division` | 时值精度（默认 480） |
| `total_bars` | 总小节数 |
| `tracks[].notes[]` | 每条轨道的音符列表 |

音符对象字段：
```json
{
  "tick": 480,
  "bar": 1,
  "pos_in_bar": 1.0,
  "pitch": 60,
  "pitch_name": "C4",
  "duration": 480,
  "velocity": 85,
  "lyric": "门"
}
```

## MuseScore 音色（Program Numbers）

生成器使用的 GM 音色映射：

| 轨道 | 音色 | Program |
|------|------|---------|
| 吉他 | Nylon Guitar | 24 |
| solo吉他 | Steel Guitar | 25/26 |
| 主唱 | Voice Oohs | 54 |
| 和声 | Choir Aahs | 52 |
| 氛围pad | String Ensemble | 48 |
| 贝斯 | Electric Bass | 33 |
| 其他 | Acoustic Grand Piano | 0 |

> **注意**：MuseScore 默认内置 `MuseScore_General.sf3` 音质较平，
> 如需真实吉他音效，可在 MuseScore 中切换为 **MuseSounds** 免费音色。

## 与 song_engineer 的关系

- **上游**：song_engineer 产出 `track/*.json` / `*.mid`
- **本技能**：生成 `.mscx` 乐谱供 MuseScore 编辑
- **协同**：MuseScore 编辑后 → `mscx_reader.py` 读取 → song_engineer 更新工程

典型流程：
```
song_engineer → track/*.mid
    ↓
musescore-cooperate → track/musescore/*.mscx
    ↓ MuseScore 编辑（修正音符/歌词/排版）
    ↓
mscx_reader.py → *.json（导回工程）
    ↓
song_engineer → 合并编辑结果
```

## MuseScore 下载

- 官网：https://musescore.org/zh-hans（免费开源）
- MuseSounds 免费音色：安装 MuseScore 后，打开 MuseHub 搜索免费音色包

## 限制

- `.mscx` 生成为简化版本（单声部、无和弦/琶音装饰），MuseScore 打开后可进一步美化
- 歌词需在 MuseScore 中手动添加（`Ctrl+L`）
- 多轨总谱 `full_score.mscx` 每轨单独一个 Staff，MuseScore 中可拖拽调整排版


# 查阅
[musescore](../../../md/kb_repo/info/text_score_xml/musescore)
## MSCX 格式规范完整查阅渠道（MuseScore 原生XML乐谱格式）
- github 代码
https://github.com/musescore/
https://github.com/musescore/MuseScore/tree/main/src/importexport/musicxml

- demo
https://github.com/musescore/MuseScore/tree/main/demos
https://github.com/musescore/MuseScore/blob/main/demos/Dawn.mscx

- 模板
https://github.com/musescore/MuseScore/tree/main/share/templates
https://github.com/musescore/MuseScore/blob/main/share/templates/My_First_Score.mscx
https://github.com/musescore/MuseScore/blob/main/share/templates/04-Solo/01-Guitar/01-Guitar.mscx

## templates 目录结构
01-General
02-Choral
03-Chamber_Music
04-Solo
05-Jazz
06-Popular
07-Band_and_Percussion
08-Orchestral
CMakeLists.txt
Marching_Bass_Drums.drm
Marching_Cymbals.drm
Marching_Snare_Drums.drm
Marching_Tenors.drm
My_First_Score.mscx
categories.json
convert.json
drumset_fr.drm
orchestral.drm

## 配置文件读取
[.env](../../../.env)
主要是 musescore_ver。
例如 musescore_ver=4.7.4.260706075
## xml 说明
- version
    - <museScore version="5.00">  代表 5.0 以上的musescore 版本
    - <museScore version="4.00">  代表 4.0 以上的musescore 版本 
如 musescore_ver=4.7.4.260706075 那么 <museScore version="4.00">

## 音色库列表
### 参考文件
[musescore.sound.yml](../../../md/kb_repo/info/text_score_xml/musescore/musescore.sound.yml)
### 读取文件
[musescore.sound.yml](../../../.cache/musescore.sound.yml)

- 一般会下载 %USERPROFILE%\Muse Hub\Instruments
 .mscx 文件里 <synti>Fluid</synti>， MuseScore 用 MS Basic
 .mscx  文件里<synti>MuseSounds</synti>， MuseScore 用 MuseSounds 库
synti 的合法值：Fluid / MuseSampler / MuseSounds。
MuseScore 4 写入 MuseSounds 音色时用 MuseSounds（不是 MuseSampler）
- Muse Guitars Vol.1
库目录名实际是 Muse Guitars Vol 1（没有点）

# 混音器的选择会保存到
audiosettings.json 而不是 .mscx 里
  01_吉他.mscx          ← 乐谱(音符/调号)，不含音色
  audiosettings.json    ← ★ 音色配置在这！每轨的 MuseSounds 音色
  score_style.mss       ← 谱面样式
  META-INF/container.xml← 清单

## audiosettings.json
每个 track 的核心是 in.resourceMeta，MuseSounds 音色的关键字段：
  - type: "muse_sampler_sound_pack"
  - vendor: "MuseSounds"
  - id = museUID（如 "13012"）
  - attributes: museCategory / museName / musePack / museUID / museVendorName / playbackSetupData

  而 partId 要跟 .mscx 里 <Part id="1"> 对应，instrumentId 跟 <Instrument id="guitar-steel"> 对应。

  1. 把 musescore.conf.json 里的音色配置补全（加上 museUID 和 playbackSetupData）
  2. 让生成器除了生成 .mscx，同时生成配套的 audiosettings.json + META-INF/container.xml，这样每轨开箱即用，不用手动在 Mixer 里选

  先查所有音色的 UID 和 playbackSetupData。playbackSetupData 这个字段我需要从库里确认，让我看 .spx 或 SQLite 里有没有：

