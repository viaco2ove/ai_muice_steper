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

# DiffSingerMiniEngine — 歌声合成技能 v2.0

## 概述

基于 **DiffSingerMiniEngine** 的轻量级歌声合成方案：
- **输入**：MIDI + 歌词 → `{track}.ustx.json`（ustx风格JSON：逐音符 position/duration/tone/lyric/kind/phones帧分配/note_midi_filled）
- **引擎**：ONNX Runtime（CPU 推理，无需 GPU，2-4GB RAM）
- **输出**：`track/singer/` 目录下的高清歌声音频 WAV
- **渲染器**：`scripts/render_singer.py`（薄CLI）+ `scripts/ds/` 包（配置驱动，复刻 OpenUTAU 官方输入契约）；旧脚本存档于 `scripts/test/`（勿用）

## 渲染器结构（scripts/ds/ 包）

| 模块 | 职责 |
|------|------|
| `config.py` | .env / dsconfig.yaml / vocoder.yaml 解析为 dataclass（maxDepth 分支语义） |
| `voicebank.py` | 声库定位/5份配置/音素表/语言表/dsdict-zh/4个专属emb/8个ONNX会话 |
| `g2p.py` | 汉字→音素（pypinyin + dsdict-zh.yaml） |
| `align.py` | MIDI↔歌词线性对齐、BAR_SEGS 分段、expand_gaps |
| `plan.py` | dur烘焙：SP padding、word_div 元音分组、rest 音高填充 → ustx.json |
| `predictors.py` | pitch/variance 预测（官方输入契约核心） |
| `acoustic.py` | acoustic+vocoder（f0 Hz、variance clamp、mel_base 转换） |
| `render.py` | 段调度/拼接/padding切除/重采样/写盘 |

## 官方输入契约（对照 OpenUTAU C# 源码，水声根因修复）

1. **所有 linguistic/acoustic 输入**：tokens 首尾各 pad 1 个 SP（8+8 帧），渲染后切除 8×512=4096 samples/侧；languages 按音素前缀（`zh/x→zh`，SP/AP→0）
2. **pitch 模型**：`pitch` 初值全 60、`expr` 全 1.0（0=表现力归零）、`note_midi` rest 音符用邻近非 rest 音高填充（组首用后值/组尾用前值/组中各半，全rest填60）、slur 继承前音符 rest 状态、steps=10
3. **variance 模型**：`pitch` 输入 = **midi 值**（不是 Hz！）、breathiness/voicing/tension 初值全 0、retake 全 true、steps=20
4. **acoustic**：f0=440·2^((midi-69)/12) Hz 且 rest 帧**不归零**；breathiness/voicing clamp [-96,0]、tension clamp [-10,10]；gender=0、velocity=1；depth=min(1.0, max_depth)=0.7、steps=20
5. **dur 链路**：word_div 按元音位置切分（SP/AP=元音，声母依附前一元音组）、word_dur=组内**帧数**和（不是 ticks）；预测后按 MIDI 时值强制缩放（零漂移）
6. **spk_embed 专属**：根/dsdur/dsvariance/dspitch 四个 emb 数值全不同，各喂各的（pitch 是 zhibin-pop.emb）

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
  "output_wav": "workspace/project/走在/song_engineer/track/singer/02_主唱.wav",
  "gender": 0.5
}
```
其中singer 文件 会被技能自动解压后使用

## 输入参数说明
gender：官方 GENC 参数
增加时声音会变尖锐。 减小时声音会变浑厚。 其实也不能说是厚而是一种奇怪的“厚” 感觉是口腔变“圆”了的声音。
建议范围值“-0.5”

## 输出
- `track/singer/` 直接用于生成wav 的mid 文件 {track}.mid 
- `track/singer/` 歌词文件  {track}.lyrics.txt，参考x studio 和openutau 等的歌词格式要求
- `track/singer/` 类似 ustx 的渲染计划 JSON 文件  {track}.ustx.json（固化对齐/分段/音素/ph_dur帧决策，可审计可手改）
- `track/singer/` 目录下的高清歌声音频 WAV


## 核心流程

```
用户指定的歌词和mid 文件
        │
        ▼
track/singer/{track}.mid (MIDI音轨) + track/singer/{track}.lyrics.txt (纯文本歌词)
        │
        ▼  plan阶段 (render_singer.py: ds/align.py + ds/plan.py)
        ├── 线性对齐: 1音符=1字符, '-'拖腔延续韵母, 段外R
        ├── 间隙展开(expand_gaps) + 按 BAR_SEGS 分段
        ├── pypinyin 汉字→音素, dur模型预测+按MIDI时值强制缩放
        ▼
track/singer/{track}.ustx.json  (类似ustx的json中间工程文件, 可审计/手改)
        │
        ▼  render阶段 (render_singer.py --from-plan: ds/predictors.py + ds/acoustic.py + ds/render.py)
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
./.venv/python.exe .workbuddy/skills/DiffSingerMiniEngine/scripts/render_singer.py --project 走在

# 4. 只生成中间工程文件 {track}.ustx.json（不渲染）
./.venv/python.exe .workbuddy/skills/DiffSingerMiniEngine/scripts/render_singer.py --project 走在 --plan-only

# 5. 手改 ustx.json 后重渲染（跳过plan生成, 直接用烘焙的ph_dur帧）
./.venv/python.exe .workbuddy/skills/DiffSingerMiniEngine/scripts/render_singer.py --project 走在 --from-plan

# 6. 可调扩散步数（默认官方值: acoustic=20 pitch=10 variance=20）
./.venv/python.exe .workbuddy/skills/DiffSingerMiniEngine/scripts/render_singer.py --project 走在 --steps 20 --steps-pitch 10 --steps-variance 20
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
