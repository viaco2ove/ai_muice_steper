---
name: DiffSingerMiniEngine
description: >
  基于 DiffSingerMiniEngine 的歌声合成技能。读 OpenUTAU .ustx 文件（含歌词/音素/音高曲线），
  通过 ONNX Runtime 调用轻量级 DiffSinger ONNX 模型合成高清歌声音频。
  无模型时给出清晰指引；有模型时全自动渲染到 singer/ 目录。
  Triggers on: DiffSinger、歌声合成、人声生成、主唱 wav、singer track、AI 歌手、DiffsingerMiniEngine
agent_created: true
entry_script: "scripts/render_singer.py"
params: {"--project": "歌曲名(required)", "--track": "音轨名(default 02_主唱)"}
executable: true
---

# DiffSingerMiniEngine — 歌声合成技能 v1.0

## 概述

基于 **DiffSingerMiniEngine** 的轻量级歌声合成方案：
- **输入**：OpenUTAU .ustx 文件（含逐音符歌词/音素/音高曲线/时长）
- **引擎**：ONNX Runtime（CPU 推理，无需 GPU，2-4GB RAM）
- **输出**：`track/singer/` 目录下的高清歌声音频 WAV

## 输入
mid文件和歌词（格式是非直接可用的）
歌手： 默认位  diffsinger_acoustic.onnx 和 hifigan_vocoder.onnx 这两个模型

## 输出
- `track/singer/` 直接用于生成wav 的mid 文件 {track}.mid 
- `track/singer/` c歌词文件  {track}.lyrics.txt
- `track/singer/` 目录下的高清歌声音频 WAV


## 核心流程

```
用户指定的歌词和mid 文件
        │
        ▼
        
track/singer/{track}.mid (MIDI音轨) + track/singer/{track}.lyrics.txt (纯文本歌词)
        │
        ▼
  render_singer.py
        │
        ├── 解析 lyrics + tone + duration + pitch (from ustx YAML)
        ├── pypinyin 汉字→音素
        ├── 检查 assets/ 模型文件
        │     ├── 有模型 → ONNX Runtime 推理 → WAV
        │     └── 无模型 → 报错退出 + 提示如何下载模型
        │
        ▼
  track/singer/02_主唱.wav
```

## ONNX 模型说明

DiffSingerMiniEngine 依赖三组 ONNX 文件（放在 `assets/` 对应子目录）：

| 类型 | 目录 | 文件 |
|------|------|------|
| 声学模型 | `assets/acoustic/` | `acoustic.onnx` |
| 声码器 | `assets/vocoder/` | `vocoder.onnx` |
| 节奏预测 | `assets/rhythmizer/` | `rhythmizer.onnx` |

**模型来源**：从 ModelScope / HuggingFace 下载 ONNX 格式声库（如 ACG-DiffSinger-VoiceDB）。
下载后放到对应目录即可，无需额外配置。

## 使用方法

```bash
# 1. 检查模型是否存在
ls .workbuddy/skills/DiffSingerMiniEngine/assets/

# 2. 如无模型，按下方"模型下载"步骤下载

# 3. 渲染主唱（默认 02_主唱）
./.venv/python.exe .workbuddy/skills/DiffSingerMiniEngine/scripts/render_singer.py --project 走在

# 4. 指定其他音轨
./.venv/python.exe .workbuddy/skills/DiffSingerMiniEngine/scripts/render_singer.py --project 走在 --track 02_主唱
```

## 模型下载

### 方式一：ModelScope（推荐，国内速度快）
```bash
# 注册 https://www.modelscope.cn
# 搜索 ACG-DiffSinger-VoiceDB 或具体歌手名
# 下载 ONNX 格式声库压缩包
# 解压到 assets/ 对应子目录
```

### 方式二：HuggingFace
```
https://huggingface.co/spaces/SJTU/diffsinger-webui
https://huggingface.co/models?search=diffsinger
```

### 方式三：自制 ONNX 模型
参考 [DiffSinger](https://github.com/openvpi/DiffSinger) 仓库：
```bash
git clone https://github.com/openvpi/DiffSinger
cd DiffSinger
# 训练或转换已有模型为 ONNX 格式
python scripts/export_onnx.py --config configs/your_singer.yaml
```

## 依赖

- Python 包：`onnxruntime` `PyYAML` `soundfile` `pypinyin` `numpy`
- 硬件：CPU 推理，无需 GPU（2-4GB RAM）

安装：
```bash
pip install onnxruntime PyYAML soundfile pypinyin
```

## 已知限制

- **必须有声库模型**：ONNX 模型文件需用户自行下载，无模型则脚本退出并提示
- **中文歌词优先**：pypinyin 汉字→音素映射针对中文优化
- **ustx 必须有歌词**：.ustx 文件的 voice_parts[].notes[].lyric 字段非空

## 相关技能

- `openutau_lyrics` — OpenUTAU 音素歌词生成（上游）
- `xstudio_lyrics` — X Studio 歌词生成（备选方案）
- `remix-master` — 混音（下游：主唱干声参与混音）
