---
name: wav_mid_human
description: 人声WAV转MIDI技能，产出可听出旋律线的干净MIDI。专门解决pyin逐帧转换产生的密密麻麻碎音问题。当用户想把人声哼唱/干声转成可听旋律MIDI、抱怨MIDI乱码碎音、需要清洗人声MIDI时触发。触发词：人声转MIDI、wav转mid、旋律线MIDI、干净MIDI、清洗碎音、听出旋律、hum to midi。
agent_created: true
---

# Wav Mid Human - 人声 WAV 转可听旋律 MIDI

## 概述

本技能专门解决 `audio_chord_recognizer` 的 `recognize_melody.py` 产出的 MIDI 碎音问题。后者用 pyin 逐帧提取（约 23ms/帧）仅做相邻同音合并，导致 57% 音符是 <50ms 的碎音，根本听不出旋律线。

本技能在 pyin 基础上加 **8 步清洗管线**，产出平均时长 >0.5s、碎音率 <5% 的可听旋律 MIDI。

**实测效果**（vocals.wav）：音符数 196→29，碎音率 57.1%→0.0%，平均时长 0.084s→0.524s。

## 触发词

人声转MIDI、wav转mid、旋律线MIDI、干净MIDI、清洗碎音、听出旋律、hum to midi

## 与 audio_chord_recognizer 的区别

| 维度 | audio_chord_recognizer/recognize_melody.py | wav_mid_human |
|------|-------------------------------------------|---------------|
| 定位 | 帧级音高转MIDI（频谱分析副产品） | 可听旋律线MIDI（专门为人声优化） |
| 碎音率 | ~57% | <5% |
| 最小音符时长 | 无过滤（10ms 碎音都保留） | 80ms（可配） |
| 中值滤波 | 无 | 有（消除单帧跳变） |
| 跳变修正 | 无 | 有（消除八度误判） |
| 音域过滤 | 无（呼吸/底噪误判为音符） | 有（限定人声音域） |
| 用途 | 音高分布统计、粗略分析 | 导入DAW/生成旋律参考/可听 |

**不替代** audio_chord_recognizer（它还做和弦识别、分轨），只替代其"旋律转MIDI"的质量。需要可听MIDI时用本技能。

## 环境准备

复用项目 `.venv`（路径：`./.venv/python.exe`）。已装依赖：
- basic_pitch（神经网络后端，优先）+ onnxruntime（推理引擎，无需 TensorFlow）
- librosa 0.11.0（pyin 后端，fallback）+ soundfile（加载）
- mido / numpy / scipy

**后端选择逻辑**：basic_pitch 用 onnxruntime 加载自带 nmp.onnx 模型，不依赖 TensorFlow（曾因 TF 依赖链损坏不可用，已通过 onnxruntime 绕过）。若 onnxruntime 缺失则自动降级到 pyin 后端。

**环境修复记录**（曾踩的坑，供参考）：venv 里的 absl-py/audioread 是残包（无版本元数据），导致 TF/librosa 导入失败；已用 `pip install --ignore-installed --no-deps` 覆盖重装正规的 absl-py、audioread，并装 onnxruntime 绕开 TF。详见 memory/2026-07-27.md。

## 快速使用

### 推荐：basic_pitch 后端（神经网络，贴合人声轮廓）
```bash
./.venv/python.exe .workbuddy/skills/wav_mid_human/scripts/wav_to_midi_bp.py   <输入.wav> -o <输出目录>
```

示例：
```bash
./.venv/python.exe .workbuddy/skills/wav_mid_human/scripts/wav_to_midi_bp.py   workspace/audio_output/沙发小曲/tracks/vocals.wav   -o workspace/audio_output/沙发小曲/melody_basicpitch
```
输出 melody_basicpitch.mid + .csv（带 velocity 起伏）。

### 备选：pyin 后端（无 onnxruntime 时用，干净但轮廓被平滑）
```bash
./.venv/python.exe .workbuddy/skills/wav_mid_human/scripts/wav_to_midi.py   <输入.wav> -o <输出目录>
```

### 带伴奏素材
先用 audio_chord_recognizer 分轨取 vocals，再转（两个后端任选）。


## 参数

| 参数 | 默认 | 说明 |
|------|------|------|
| `--fmin` | 80 Hz | 人声最低频率（男声可降到70） |
| `--fmax` | 800 Hz | 人声最高频率（女声可升到1000） |
| `--min-dur` | 0.08s | 最小音符时长，低于此的碎音丢弃 |
| `--median-win` | 5 | 中值滤波窗口（奇数，越大越平滑） |
| `--max-jump` | 7 | 跳变修正阈值半音，相邻帧超过此视为误判 |
| `--merge-tol` | 1 | 合并容差半音，相邻帧差≤此值合并为同音 |
| `--hop` | 512 | pyin hop_length |

**调参建议**：
- 还是有碎音 → 提高 `--min-dur`（0.10~0.15）
- 音符被过度合并 → 降低 `--merge-tol` 到 0 或减小 `--median-win`
- 音域误判多 → 收紧 `--fmin`/`--fmax` 到实际人声范围

## 输出

```
<输出目录>/
├── melody_human.mid       # 干净单轨钢琴MIDI，可听旋律线
├── melody_human.csv       # 音符表（起止时间/时长/音名/MIDI/帧数）
└── quality_report.md      # （用 compare_quality.py 生成）与旧版对比
```

### 旋律音符表（melody_human.csv）
| start | end | duration | note | midi | frames |
|-------|-----|----------|------|------|--------|
| 0.876 | 1.245 | 0.369 | A3 | 57 | 16 |

## 质量对比

对比新旧 MIDI 质量：
```bash
./.venv/python.exe .workbuddy/skills/wav_mid_human/scripts/compare_quality.py \
  <旧.mid> <新.mid> -o quality_report.md
```

输出碎音率/音域/音符数/平均时长的对比表与结论。

## 8 步清洗管线

```
输入WAV
  │
  ├─1. 加载（soundfile，转mono）
  ├─2. 预处理（归一化 + noise gate 压底噪/呼吸）
  ├─3. pyin 音高提取（f0/voiced/prob）
  ├─4. 有声帧过滤（丢弃无声帧，不生成碎片段）
  ├─5. 中值滤波（消除单帧跳变）
  ├─6. 跳变修正（短时八度跳变视为误判）
  ├─7. 音符合并（连续相近帧合并，取中位数为代表音高）
  ├─8. 碎音过滤（<min_dur 丢弃 + 音域外丢弃）
  ▼
干净MIDI
```

每步原理详见 [references/wav_to_mid_principles.md](references/wav_to_mid_principles.md)。
使用场景详见 [references/usage_examples.md](references/usage_examples.md)。

## 局限性

1. **依赖输入质量**：输入必须是干净干声。带伴奏/重混响的素材需先用 audio_chord_recognizer 分轨取 vocals、或消混响。
2. **pyin 精度上限**：极快速乐句/气声起音可能仍漏识别。basic_pitch/crepe 精度更高但当前环境缺 TF 无法用。
3. **不识歌词**：只转音高，不区分字。如需逐字音名对齐，用 song_engineer 的 AI 设计旋律（track/02_主唱）。
4. **参数需按素材调**：男声/女声/不同曲风可能需调 fmin/fmax/min-dur。

## 建议
建议用户使用UVR5分人声 → Melodyne提取MIDI。
https://www.jb51.net/softs/756345.html

## 参考

- 清洗原理：`references/wav_to_mid_principles.md`
- 使用示例：`references/usage_examples.md`
- 问题根源：`md/kb_repo/info/wav_to_mid.md`
- 原始脚本（对照）：`.workbuddy/skills/audio_chord_recognizer/scripts/recognize_melody.py`