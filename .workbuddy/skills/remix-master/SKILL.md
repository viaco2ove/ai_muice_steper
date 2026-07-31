---
name: remix-master
description: 配置驱动混音技能。读 remix.json 配置每条音轨的音量/增益/静音/声像，混合成最终母带 wav。优先用真实干声 wav（如 OpenUTAU 导出的主唱），改配置重混立即见效。触发词：混音、remix、放大主唱、调音量、音轨平衡、母带、调音、声音太小、主唱听不见。
agent_created: true
entry_script: "scripts/remix.py"
params: {"--project": "歌曲名", "--track-dir": "音轨目录"}
executable: true
---

# Remix Master - 配置驱动混音

## 解决什么问题

之前"放大主唱没有效果"，根本原因是：旧混音脚本对主唱轨是用 FluidSynth 重新合成人声音色（program=54），**根本没读取 OpenUTAU 导出的真实主唱干声 `02_主唱.wav`**。所以调主唱音量参数，改的是合成人声，真正的人声干声从没进过混音，自然"没有效果"。

本技能的核心：**主唱轨默认直接用 `02_主唱.wav` 真实干声**（OpenUTAU 导出），改 `remix.json` 里主唱的 `gain_db`/`vol` 后重混，主唱在最终 wav 里立即被放大/缩小，所见即所得。

## 触发词

混音、remix、放大主唱、调音量、音轨平衡、母带、调音、声音太小、主唱听不见

## 核心思路

```
remix.json（每轨 vol/gain_db/mute/pan/source）
        │
        ▼
   remix.py  ──► 逐轨解析音源：
        │         ① 优先 <track>.wav 真实干声（主唱走这条 ✓）
        │         ② fallback <track>.mid + FluidSynth 合成（吉他等）
        ▼
   叠加 + 母带（归一化/限幅）-> full_remix.wav
```

**source 字段是关键**，决定一条轨用真实干声还是 MIDI 合成：

| source | 行为 |
|--------|------|
| `auto`（默认） | 优先 `<track>.wav` 真实干声；找不到才 fallback 到 `<track>.mid` 合成 |
| `wav` | 强制用 wav 干声（不存在则跳过并告警） |
| `midi` | 强制 `<track>.mid` 走 FluidSynth 合成（program/soundfont 从 `<track>.json` 读） |

主唱 `02_主唱.wav` 是 OpenUTAU 导出的真人声，默认 `source=auto` 就会用它。

## remix.json 配置规范

位置：`workspace/project/{歌名}/song_engineer/remix.json`

```json
{
  "schema": "remix.v1",
  "song": "走在",
  "bpm": 68,
  "tracks": {
    "02_主唱": {
      "source": "auto",
      "vol": 1.0,
      "gain_db": 3.0,
      "mute": false,
      "pan": 0.0,
      "comment": "放大主唱 -> 调 gain_db 或 vol"
    },
    "01_吉他": { "source": "auto", "vol": 0.7, "gain_db": 0.0, "mute": false, "pan": 0.0 },
    "13_轻贝斯": { "source": "auto", "vol": 0.5, "gain_db": 0.0, "mute": false, "pan": 0.0 },
    "09_和声": { "source": "auto", "vol": 0.4, "gain_db": 0.0, "mute": false, "pan": 0.0 }
  },
  "master": {
    "normalize": true,
    "target_peak": 0.95,
    "limiter": true,
    "output": "workspace/project/走在/song_engineer/track/full_remix.wav"
  }
}
```

### 字段说明

| 字段 | 作用 | 取值 |
|------|------|------|
| `source` | 音源类型 | `auto` / `wav` / `midi`（见上表） |
| `vol` | 线性音量倍率 | 0.0 ~ 2.0（1.0=原音量，0.7=减小，1.5=放大） |
| `gain_db` | 分贝增益 | -12 ~ +12（+6 约翻倍，-6 约减半，0=不变） |
| `mute` | 静音该轨 | `true` / `false` |
| `pan` | 声像 | -1（左）~ +1（右），0=居中 |
| `comment` | 备注 | 任意文字 |

**音量计算**：最终幅度 = `vol × 10^(gain_db/20)`。`vol` 和 `gain_db` 同时生效，相乘。

**调音量用哪个**：
- 放大/缩小单条轨 → 调 `gain_db`（分贝，听感线性，+3 明显变大、+6 翻倍）
- 比例平衡 → 调 `vol`（如吉他 0.7、人声 1.0）

### master 段

| 字段 | 作用 |
|------|------|
| `normalize` | 叠加后整体归一化到 target_peak |
| `target_peak` | 归一化目标峰值（0.95 留一点 headroom） |
| `limiter` | 硬限幅防削波（叠加爆音时裁剪到 ±1.0） |
| `output` | 输出 wav 路径 |

## 用法

### 三步流程

```bash
# 1. 自动生成默认 remix.json（扫描 track 目录下所有 wav）
./.venv/python.exe .workbuddy/skills/remix-master/scripts/remix.py --project 走在 --init

# 2. 编辑 remix.json（如把 02_主唱 的 gain_db 改成 3.0 放大主唱）

# 3. 重混
./.venv/python.exe .workbuddy/skills/remix-master/scripts/remix.py --project 走在
# -> full_remix.wav，主唱已放大
```

### 参数

| 参数 | 默认 | 说明 |
|------|------|------|
| `--project` | 走在 | 歌名，定位 `workspace/project/{歌名}/song_engineer/track` |
| `--track-dir` | 自动推导 | 直接指定音轨目录 |
| `--remix` | `{song_engineer}/remix.json` | 指定 remix.json 路径 |
| `--init` | - | 扫描生成默认配置后退出 |
| `-o/--output` | remix.json 的 master.output | 覆盖输出路径 |

### 验证主唱是否真的进去了

脚本结尾会打印每轨音源，重点关注主唱：

```
★ 主唱音源: wav:02_主唱.wav  (真实干声 ✓ 改 gain_db 立即生效)
```

- 看到 `wav:02_主唱.wav` → 用的是真实人声干声，改 `gain_db` 立即生效 ✓
- 看到 `midi:02_主唱.mid` → 用的是合成人声（不是真人声），需检查 `02_主唱.wav` 是否存在

## 与其他技能的关系

- **上游**：`song_engineer`（分轨 json/mid/wav 产物）、`openutau_lyrics` / `wav_mid_human`（真人声干声导出）
- 本技能只读 `track/*.wav` / `*.mid` / `*.json` 和 `remix.json`，不修改任何上游产物
- remix.json 是独立配置文件，与 song_engineer.json 解耦，专门管混音参数

## 重要限制

- 本技能聚焦**音量/静音/声像/母带归一化**，不做 EQ/压缩/混响等高级混音（简单可控）
- 主唱真实人声必须是 wav 干声（OpenUTAU 导出的 `02_主唱.wav`）；若只有 midi，fallback 合成的不是真人声
- 乐器轨若无 wav 干声，fallback 到 FluidSynth + SoundFont 合成（音质取决于 sf2，属"塑料音色"验证级，详见 [FluidSynth.md](../../../md/kb_repo/info/FluidSynth.md)）

## 依赖

- `.env` 配置 `fluidsynth_path` / `soundfonts_path`（仅 midi fallback 合成时需要）
- Python 包：`numpy` / `soundfile` / `scipy`（重采样）/ `fluidsynth`+`mido`（midi 合成时）
