# audio_chord_recognizer 使用指南

## 环境准备

### 方式一：一键安装（推荐）

```bash
# 进入项目目录
cd D:\Users\viaco\PycharmProjects\ai_muice_steper

# 用 Python 直接运行安装脚本
python .workbuddy/skills/audio_chord_recognizer/scripts/setup.py
```

### 方式二：手动 conda + pip

```bash
# 1. 创建 conda 虚拟环境
conda create -p ./.venv python=3.11 -y
conda activate ./.venv

# 2. 安装依赖（使用阿里云镜像）
pip install librosa basic-pitch demucs mido torch numpy scipy \
  -i https://mirrors.aliyun.com/pypi/simple/
```

> **注意**：torch 默认安装 CPU 版本，无需 NVIDIA 显卡。如需 CUDA 加速：
> ```bash
> pip install torch --index-url https://download.pytorch.org/whl/cu118
> ```

---

## 脚本使用说明

### 1. setup.py — 依赖安装

```bash
python .workbuddy/skills/audio_chord_recognizer/scripts/setup.py
```

自动检测 Python 版本，检查 pip，依次安装全部依赖，最后验证核心包是否可用。

---

### 2. separate_tracks.py — 音轨分离

```bash
python scripts/separate_tracks.py <input_file> -o <output_dir> [选项]
```

**参数：**

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `input` | 输入音频文件 | 必填 |
| `-o, --output` | 输出目录 | `tracks` |
| `-m, --model` | demucs 模型 | `htdemucs` |
| `-d, --device` | cpu / cuda | 自动 |

**可用模型：**
- `htdemucs` — 默认，平衡速度和精度
- `htdemucs_ft` — 更高精度，速度更慢
- `sdxm` — 更轻量

**输出文件：**

| 文件 | 内容 |
|------|------|
| `vocals.wav` | 人声 |
| `drums.wav` | 鼓组 |
| `bass.wav` | 贝斯 |
| `other.wav` | 其他乐器（最适合做和弦识别） |

**示例：**
```bash
python scripts/separate_tracks.py my_song.mp3 -o tracks/
```

---

### 3. recognize_chords.py — 和弦识别

```bash
python scripts/recognize_chords.py <input_file> -o <output.txt> [选项]
```

**参数：**

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `input` | 输入音频文件 | 必填 |
| `-o, --output` | 输出文件 | 必填 |
| `--hop` | 滑动步长（秒） | `0.5` |
| `--window` | 分析窗口长度（秒） | `0.5` |

**输出格式（chords.txt）：**
```
# 和弦识别结果
# 格式: 时间(秒)  和弦  置信度
# 根音: C C# D D# E F F# G G# A A# B
# 类型: maj/min/maj7/min7/7/sus4/sus2/dim/aug

0.00  C:maj      0.851
0.50  G:min      0.782
1.00  Am         0.823
```

**支持的和弦类型：**
- 大三和弦 `maj`（如 `C:maj`）
- 小三和弦 `min`（如 `Am`）
- 大七和弦 `maj7`（如 `Cmaj7`）
- 小七和弦 `min7`（如 `Am7`）
- 属七和弦 `7`（如 `G7`）
- 挂四和弦 `sus4`（如 `Dsus4`）
- 挂二和弦 `sus2`（如 `Csus2`）
- 减三和弦 `dim`（如 `Bdim`）
- 增三和弦 `aug`（如 `Caug`）

**提示：** 对 `other.wav`（伴奏轨）识别效果最好，避免人声干扰。

---

### 4. recognize_melody.py — 旋律识别

```bash
python scripts/recognize_melody.py <input_file> -o <output_dir> [选项]
```

**参数：**

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `input` | 输入音频文件 | 必填 |
| `-o, --output` | 输出目录 | `melody` |
| `--fmin` | 最低检测频率 Hz | `80` |
| `--fmax` | 最高检测频率 Hz | `1000` |
| `--velocity` | MIDI 音符力度 1-127 | `80` |

**输出文件：**

| 文件 | 说明 |
|------|------|
| `pitch.csv` | 时间、频率、音名、MIDI编号、置信度 |
| `melody.mid` | librosa.pyin 生成的 MIDI |
| `basic_pitch.mid` | Spotify basic-pitch 生成的 MIDI（可选）|

**pitch.csv 格式：**
```csv
time,freq,note,midi,prob
0.000,440.00,A4,69,0.892
0.011,442.00,A4,69,0.901
0.023,445.00,A4,69,0.887
```

**提示：** 对 `vocals.wav`（人声轨）识别效果最好。

---

### 5. full_analysis.py — 一键全流程（推荐）

```bash
python scripts/full_analysis.py <input_file> -o <output_dir>
```

一次性完成全部分析，输出结构：
```
<output_dir>/
├── tracks/          # 4 个分离音轨 wav
├── chords.txt       # 和弦时间线
├── melody/
│   ├── pitch.csv
│   └── melody.mid
└── report.md       # 完整分析报告
```

**report.md 包含：**
1. 音轨分离结果（4轨）
2. 和弦进行时间线 + 频率统计
3. 旋律音符序列（前20个）
4. 分析摘要（调性、情绪、风格推断）

---

## 常见问题

### Q: demucs 首次运行报模型下载错误？
A: demucs 首次会自动下载模型（约 80MB）。如遇网络问题，可手动下载：
```bash
# 手动指定模型路径，或设置代理
export HTTPS_PROXY=http://127.0.0.1:7890
```

### Q: torch 装不上？
A: 确认 pip 版本足够新：
```bash
pip install --upgrade pip
pip install torch -i https://mirrors.aliyun.com/pypi/simple/
```
如无 NVIDIA 显卡，默认 CPU 版本即可。

### Q: basic-pitch 导入报错？
A: basic-pitch 需要 tensorflow，如不需要可选装：
```bash
pip install basic-pitch -i https://mirrors.aliyun.com/pypi/simple/
```
即使 basic-pitch 失败，librosa.pyin 旋律识别仍可用。

### Q: 和弦识别结果不准？
A: 可能原因：
- 人声干扰 → 改用 `other.wav`（伴奏轨）
- 采样率不对 → 脚本自动重采样为 44100Hz
- 窗口太大 → 减小 `--hop` 和 `--window` 参数

### Q: 旋律识别漏音/漂移？
A: 调整频率范围：
```bash
# 降低最低频率（检测低音人声）
python scripts/recognize_melody.py vocals.wav -o out/ --fmin 60

# 升高最高频率（检测高音）
python scripts/recognize_melody.py vocals.wav -o out/ --fmax 1200
```

### Q: 输出中文乱码？
A: 所有脚本均使用 UTF-8 编码。确保终端编码为 UTF-8：
```bash
chcp 65001
```

---

## 技术原理简述

| 模块 | 核心算法 | 原理 |
|------|---------|------|
| 音轨分离 | demucs (HTDemucs) | 深度学习 U-Net 源分离 |
| 和弦识别 | librosa chroma_cqt | 恒Q变换提取音高能量，余弦相似度匹配和弦模板 |
| 旋律识别 | librosa.pyin | 神经网络基频追踪（PYiN 算法） |
| 旋律识别 | basic-pitch | Spotify CNN 音频转 MIDI |