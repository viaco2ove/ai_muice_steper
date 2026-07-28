# 使用示例与场景

wav_mid_human 技能支持双后端,3 个典型使用场景。

**后端选择**:
- **basic_pitch(`wav_to_midi_bp.py`)**:神经网络,贴合人声轮廓,带 velocity,推荐默认用
- **pyin(`wav_to_midi.py`)**:8步清洗,干净但轮廓被平滑,无 onnxruntime 时用

---

## 场景 1:纯干声转 MIDI(最常见)

已有干净的人声干声 wav(无伴奏、少混响),直接转。

### 推荐:basic_pitch 后端
```bash
./.venv/python.exe .workbuddy/skills/wav_mid_human/scripts/wav_to_midi_bp.py \
  vocals.wav -o output/
```
输出 `melody_basicpitch.mid` + `.csv`(带 velocity 起伏,贴合人声)。

### 备选:pyin 后端
```bash
./.venv/python.exe .workbuddy/skills/wav_mid_human/scripts/wav_to_midi.py \
  vocals.wav -o output/
```
输出 `melody_human.mid` + `.csv`(干净,但细微起伏被中值滤波抹平)。

**适用**:自己录的哼唱干声、UVR5/demucs 分离后的纯人声、无伴奏清唱录音。

**预期**:直接得到可听旋律 MIDI,碎音率 <5%。

---

## 场景 2:带伴奏的素材(需先分轨)

整首歌曲混合 wav,人声和伴奏叠加。**必须先分离人声**再转(kb 文档第三章1)。

```bash
# Step 1: 用 audio_chord_recognizer 分轨取 vocals
./.venv/python.exe .workbuddy/skills/audio_chord_recognizer/scripts/separate_tracks.py \
  song.wav -o tracks/

# Step 2: 对 vocals 转可听 MIDI(basic_pitch 后端)
./.venv/python.exe .workbuddy/skills/wav_mid_human/scripts/wav_to_midi_bp.py \
  tracks/vocals.wav -o melody_basicpitch/
```

**为什么不能直接转整曲**:kb 文档第三章1 明确,鼓/贝斯/和声频率与人声叠加,算法分不清主旋律,多频率全部生成音符,彻底混乱。先分轨是硬要求。

**实测案例**(本项目):
```bash
# 已有分轨:workspace/audio_output/沙发小曲/tracks/vocals.wav
./.venv/python.exe .workbuddy/skills/wav_mid_human/scripts/wav_to_midi_bp.py \
  workspace/audio_output/沙发小曲/tracks/vocals.wav \
  -o workspace/audio_output/沙发小曲/melody_basicpitch

# 对比质量(与旧版 pyin 原 MIDI)
./.venv/python.exe .workbuddy/skills/wav_mid_human/scripts/compare_quality.py \
  workspace/audio_output/沙发小曲/melody/melody.mid \
  workspace/audio_output/沙发小曲/melody_basicpitch/melody_basicpitch.mid \
  -o workspace/audio_output/沙发小曲/melody_basicpitch/quality_vs_old.md
```

结果:音符数 196->45,碎音率 57.1%->0.0%,平均时长 0.084s->0.268s,带 velocity 起伏。

---

## 场景 3:调参优化(素材质量一般时)

### basic_pitch 后端调参
```bash
# 还是有碎音:提高 onset 阈值(更严格) + 加大最小音符长度
./.venv/python.exe .workbuddy/skills/wav_mid_human/scripts/wav_to_midi_bp.py \
  vocals.wav -o out/ --onset 0.7 --min-len 150

# 音符太少(漏识别):降低 onset 阈值
./.venv/python.exe .workbuddy/skills/wav_mid_human/scripts/wav_to_midi_bp.py \
  vocals.wav -o out/ --onset 0.35

# 限定音域(过滤低频噪音/高频泛音误判)
./.venv/python.exe .workbuddy/skills/wav_mid_human/scripts/wav_to_midi_bp.py \
  vocals.wav -o out/ --fmin 80 --fmax 800
```

### pyin 后端调参
```bash
# 还是有碎音:提高最小音符时长 + 加大中值滤波窗口
./.venv/python.exe .workbuddy/skills/wav_mid_human/scripts/wav_to_midi.py \
  vocals.wav -o out/ --min-dur 0.12 --median-win 7

# 音符被过度合并(快速乐句丢了)
./.venv/python.exe .workbuddy/skills/wav_mid_human/scripts/wav_to_midi.py \
  vocals.wav -o out/ --merge-tol 0 --median-win 3 --min-dur 0.06

# 男声/女声音域调整
./.venv/python.exe .workbuddy/skills/wav_mid_human/scripts/wav_to_midi.py \
  male_vocals.wav -o out/ --fmin 70
```

---

## 两个后端怎么选

| 情况 | 用哪个 |
|------|--------|
| 想要最贴合人声、带力度起伏 | basic_pitch(`wav_to_midi_bp.py`) |
| onnxruntime 不可用 | pyin(`wav_to_midi.py`) |
| 需要快速出结果(basic_pitch 需 20-60s) | pyin(更快) |
| 想对比两种结果 | 都跑一遍,用 compare_quality.py 对比 |

---

## 与 song_engineer 工程的配合

wav_mid_human 是通用工具技能,不绑定特定歌曲。但在 song_engineer 工程中可作为"真实人声旋律参考"来源:

1. 用本技能把哼唱干声转成可听 MIDI(basic_pitch 优先)
2. 在 song_engineer 诊断时对照 AI 设计旋律(track/02_主唱)与真实哼唱 MIDI 的差异
3. 帮助校准 AI 设计旋律的音高走向

**注意**:本技能只转音高不识歌词。若需"逐字音名对齐"(每个字对应一个音),用 song_engineer 的 AI 设计旋律能力(基于歌词韵律+和声约束生成),而非本技能。

---

## 输出文件用途

| 文件 | 用途 |
|------|------|
| melody_basicpitch.mid / melody_human.mid | 导入 DAW/播放器试听、作为旋律参考轨 |
| melody_basicpitch.csv / melody_human.csv | 程序读取音符序列、分析音高分布 |
| quality_report.md | 量化清洗效果、对比不同参数/不同后端 |

---

## 故障排查

| 现象 | 原因 | 解决 |
|------|------|------|
| 报"缺少 basic_pitch" | basic_pitch 未装或导入失败 | 检查 onnxruntime/absl-py/audioread 是否完好(见 SKILL.md 环境修复记录) |
| basic_pitch 报模型无法加载 | onnxruntime 缺失 | `pip install onnxruntime` |
| 报错 audioread available_backends | audioread 残包 | `pip install --ignore-installed --no-deps audioread` |
| 报错 absl flags | absl-py 残包 | `pip install --ignore-installed --no-deps absl-py` |
| pyin 音符数太少 | 素材太短或无声帧多 | 检查 wav 是否真为人声、降低 min-dur |
| 音高整体偏低/偏高 | fmin/fmax 不匹配 | 按男/女声调整 |