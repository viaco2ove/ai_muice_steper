---
name: DiffSingerMiniEngine
description: >
  基于 DiffSingerMiniEngine 的歌声合成技能。mid+歌词先生成 ustx风格中间工程文件
  {track}.ustx.json（逐音符歌词/音素/时长帧/分段决策），再经 ONNX Runtime 合成高清歌声音频。
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
- **输入**：MIDI + 歌词 → `{track}.ustx.json`（ustx风格JSON：逐音符 position/duration/tone/lyric/kind/phones帧分配）
- **引擎**：ONNX Runtime（CPU 推理，无需 GPU，2-4GB RAM）
- **输出**：`track/singer/` 目录下的高清歌声音频 WAV

## 配置文件
.env 文件
- 配置了 singers_path
例如 D:\OpenUtau\Singers\Singers\YunYe_DiffSinger_CE_26.07.16.zip
- diff_singer_mini_engine_assets
例如 D:\OpenUtau\Singers\Singers\assets
保存oonx 等文件资源的路径

## 输入
mid文件和歌词（格式是非直接可用的）
歌手： 默认位  diffsinger_acoustic.onnx 和 hifigan_vocoder.onnx 这两个模型

也可以输入一个json 文件。例如
```
{
  "input_mid": "workspace/project/走在/song_engineer/track/02_主唱.mid",
  "input_lyrics": "workspace/project/走在/song_engineer/track/03_lyrics.json",
  "singer": "D:\\OpenUtau\\Singers\\Singers\\YunYe_DiffSinger_CE_26.07.16.zip",
  "output_mid": "workspace/project/走在/song_engineer/track/singer/02_主唱.mid",
  "output_lyrics": "workspace/project/走在/song_engineer/track/singer/02_主唱.lyrics.txt",
  "output_ustx_json": "workspace/project/走在/song_engineer/track/singer/02_主唱.ustx.json",
  "output_wav": "workspace/project/走在/song_engineer/track/singer/02_主唱.wav"
}
```
其中singer 文件 会被技能自动解压后使用

## 输出
- `track/singer/` 直接用于生成wav 的mid 文件 {track}.mid 
- `track/singer/` 歌词文件  {track}.lyrics.txt
- `track/singer/` 类似 ustx 的渲染计划 JSON 文件  {track}.ustx.json（固化对齐/分段/音素/ph_dur帧决策，可审计可手改）
- `track/singer/` 目录下的高清歌声音频 WAV


## 核心流程

```
用户指定的歌词和mid 文件
        │
        ▼
track/singer/{track}.mid (MIDI音轨) + track/singer/{track}.lyrics.txt (纯文本歌词)
        │
        ▼  plan阶段 (render_yunye_v2.py)
        ├── 线性对齐: 1音符=1字符, '-'拖腔延续韵母, 段外R
        ├── 间隙展开(expand_gaps) + 按 BAR_SEGS 分段
        ├── pypinyin 汉字→音素, dur模型预测+按MIDI时值强制缩放
        ▼
track/singer/{track}.ustx.json  (类似ustx的json中间工程文件, 可审计/手改)
        │
        ▼  render阶段 (render_yunye_v2.py --from-plan)
        ├── 跳过dur预测, 直接用plan烘焙的ph_dur帧
        ├── pitch → variance → acoustic → vocoder (ONNX 7步pipeline)
        ▼
  track/singer/{track}.wav
```


## 直接用于生成wav 的歌词的格式
[.workbuddy/skills/DiffSingerMiniEngine/references/lyrics.txt.md]

## 声库来源
[md/kb_repo/info/human_gen/声库来源.md]

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

# 3. 渲染主唱（默认 02_主唱）: plan+render 一气呵成
./.venv/python.exe .workbuddy/skills/DiffSingerMiniEngine/scripts/render_yunye_v2.py --project 走在

# 4. 只生成中间工程文件 {track}.ustx.json（不渲染）
./.venv/python.exe .workbuddy/skills/DiffSingerMiniEngine/scripts/render_yunye_v2.py --project 走在 --plan-only

# 5. 手改 ustx.json 后重渲染（跳过plan生成, 直接用烘焙的ph_dur帧）
./.venv/python.exe .workbuddy/skills/DiffSingerMiniEngine/scripts/render_yunye_v2.py --project 走在 --from-plan
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
- **ustx.json 可手改**：`{track}.ustx.json` 的 notes[].lyric / phones[].frames 可直接编辑后用 `--from-plan` 重渲染（如修咬字时长/换字）

## 相关技能

- `openutau_lyrics` — OpenUTAU 音素歌词生成（上游）
- `xstudio_lyrics` — X Studio 歌词生成（备选方案）
- `remix-master` — 混音（下游：主唱干声参与混音）
