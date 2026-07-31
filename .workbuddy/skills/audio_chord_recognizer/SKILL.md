---
name: audio_chord_recognizer
description: 音频和弦识别与旋律分析技能。当用户想要从音频中识别和弦进行、提取旋律生成MIDI、分离人声/伴奏，或需要AI辅助扒谱时触发。
agent_created: true
entry_script: "scripts/recognize_chords.py"
params: {"input": "音频文件路径(required)"}
executable: true
---

# Audio Chord Recognizer 技能

## 能力概览

纯本地 Python 音频分析工具集，零在线 API 依赖：

| 脚本 | 功能 |
|------|------|
| `separate_tracks.py` | 使用 demucs 分离人声/鼓/贝斯/其他 |
| `recognize_chords.py` | 基于 librosa chroma 特征 + 模板匹配识别和弦进行 |
| `recognize_melody.py` | librosa.pyin + basic-pitch 提取旋律并生成 MIDI |
| `full_analysis.py` | 一键全流程：分离 → 和弦 → 旋律 → 生成 report.md |

## 触发词

识别和弦、音频分析、和弦识别、旋律识别、吉他和弦、扒谱、分离音轨、人声分离、音频转MIDI、从音频提取旋律

## 输出目录
输出到 /workspace/audio_output/{song_name}/

## 环境准备

```bash
# 创建虚拟环境
conda create -p ./.venv python=3.11 -y
conda activate ./.venv

# 安装依赖
pip install librosa basic-pitch demucs mido torch numpy scipy -i https://mirrors.aliyun.com/pypi/simple/
```

## 快速使用

### 一键全流程分析（推荐）
```bash
python scripts/full_analysis.py input.mp3 -o output_dir/
```

### 分步使用
```bash
# 1. 分离音轨
python scripts/separate_tracks.py input.mp3 -o tracks/

# 2. 识别和弦（对伴奏轨效果更佳）
python scripts/recognize_chords.py tracks/other.wav -o chords.txt

# 3. 识别旋律
python scripts/recognize_melody.py tracks/vocals.wav -o melody/
```

## 输出说明

### full_analysis.py → report.md
- 音轨分离结果（4个文件）
- 和弦进行时间线
- 旋律音符序列
- 分析摘要（调性、BPM、情绪风格推断）

### recognize_chords.py → chords.txt
```
0.0   C:maj  0.85
0.5   G:min  0.78
1.0   Am     0.82
1.5   F:maj  0.75
```

### recognize_melody.py → pitch.csv + melody.mid
- `pitch.csv`：时间(秒)、频率(Hz)、音名、MIDI编号
- `meleline.mid`：可导入任意 DAW 或 MuseScore

## 工程聚合

本技能的产物可被 `song_engineer` 技能聚合进统一的「歌曲工程MD」。产物到工程MD区块的字段对照：

| 本技能产物字段 | 工程MD区块 | 说明 |
|---------------|-----------|------|
| report.md 旋律分析（音域/平均音高） | 旋律特征 | 音域/中心音的权威来源 |
| report.md 和弦时间线（按秒） | 和弦详情 > 和弦时间线 | 扒谱视角，与 ai_chords 的"按小节"创作视角并存 |
| report.md 分析摘要（调性/情绪） | 元信息 > 调号（参考）/ 诊断参考 | 调性推断仅作参考，权威调号取 ai_chords |
| report.md 音轨分离结果（4个wav） | 附件与引用 | 相对路径引用 |
| melody/melody.mid | 附件与引用 | 相对路径引用 |
| melody/pitch.csv | 附件与引用 | 相对路径引用 |

**聚合触发**：当用户说「初始化工程」「聚合半成品」「诊断工程」时，由 song_engineer 读取本技能产物并按上表映射。本技能本身无需改动。

**诊断关联**：song_engineer 诊断时会对照"按秒的和弦时间线"与"按小节的和弦骨架"，检查扒谱结果与创作意图是否一致（如扒谱出的实际和弦与编配和弦是否吻合）。

工程MD格式规范见：`md/currdesign/工程MD格式规范.md`

## 技术细节

- **和声识别**：librosa chroma_cqt → 余弦相似度匹配 9 种和弦模板
- **旋律识别**：librosa.pyin 基频追踪 + basic-pitch MIDI 生成，双重结果对比
- **音轨分离**：demucs v4（HTDemucs），首次运行自动下载模型（约 80MB）
- **torch**：默认 CPU 版，无需 NVIDIA 显卡
