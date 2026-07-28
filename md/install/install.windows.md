# Windows 环境安装指南

> 本文档主要供 workbuddy 等 AI 工具及开发者参考,说明在 Windows 上从零搭建 AI 音乐助手项目运行环境的完整流程。涵盖 Python 虚拟环境、音频处理库、MIDI 合成器(FluidSynth+SoundFont)、以及各 workbuddy 技能的依赖。

---

## 一、前置要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Windows | 10/11 x64 | 64 位(FluidSynth dll 需 64 位 Python) |
| Python | 3.11.x | **必须 3.11**(basic_pitch 的 onnxruntime 后端要求) |
| Git | 任意 | 克隆项目 |
| 磁盘 | ~5GB | venv 包 + FluidSynth + SoundFont |

> Python 必须是 64 位,且版本 3.11。3.12+ 可能与部分包(torchaudio/demucs)不兼容,3.10 则 basic_pitch 的 onnxruntime 路径不在官方支持范围。

---

## 二、克隆项目

```bash
git clone <项目地址> ai_muice_steper
cd ai_muice_steper
```

项目结构:
```
ai_muice_steper/
├── .workbuddy/skills/        # AI 音乐技能(audio_chord_recognizer, song_engineer, wav_mid_human 等)
├── workspace/                # 各技能输出
├── md/                       # 设计文档、知识库、安装文档
├── .env                      # FluidSynth/SoundFont 路径配置(本指南创建)
└── .venv/                    # Python 虚拟环境(本指南创建)
```

---

## 三、Python 虚拟环境

### 1. 创建 venv

```bash
python -m venv .venv
```

> 项目约定 venv 放在项目根 `.venv/`,Python 解释器为 `.venv/python.exe`。所有技能脚本都通过 `./.venv/python.exe` 调用。

### 2. 升级 pip

```bash
.venv/python.exe -m pip install --upgrade pip -i https://mirrors.aliyun.com/pypi/simple/
```

国内推荐用阿里云镜像加速(下同)。

---

## 四、音频处理库(audio_chord_recognizer + wav_mid_human)

```bash
.venv/python.exe -m pip install \
  librosa soundfile mido numpy scipy \
  -i https://mirrors.aliyun.com/pypi/simple/
```

| 包 | 用途 | 当前验证版本 |
|----|------|------------|
| librosa | pyin 音高提取、chroma 和弦识别 | 0.11.0 |
| soundfile | wav 读写(绕过 audioread 问题) | 0.14.0 |
| mido | MIDI 读写 | 1.3.3 |
| numpy | 数值计算 | 1.26.4 |
| scipy | 中值滤波 | 1.17.1 |

### 音轨分离(demucs,可选)

```bash
.venv/python.exe -m pip install demucs -i https://mirrors.aliyun.com/pypi/simple/
# 当前验证版本 4.1.0,torch CPU 版自动装
```

首次运行 demucs 会自动下载 HTDemucs 模型(~80MB)。

---

## 五、basic_pitch 神经网络后端(wav_mid_human 推荐后端)

basic_pitch 用于人声 WAV->MIDI(精度远超 pyin)。它自带 onnx 模型,但默认依赖 TensorFlow(本环境的 TF 链路损坏,见"已知坑")。**走 onnxruntime 后端绕开 TF**:

```bash
.venv/python.exe -m pip install basic-pitch onnxruntime -i https://mirrors.aliyun.com/pypi/simple/
```

| 包 | 用途 | 版本 |
|----|------|------|
| basic-pitch | Spotify 神经网络音高转 MIDI | 0.4.0 |
| onnxruntime | ONNX 推理引擎(替代 TF) | 1.28.0 |

### 验证 basic_pitch 可用

```bash
.venv/python.exe -c "from basic_pitch.inference import predict; print('OK')"
```

若报 `cannot be loaded into either TensorFlow...`,确认 onnxruntime 已装:
```bash
.venv/python.exe -c "import onnxruntime; print(onnxruntime.__version__)"
```

---

## 六、FluidSynth + SoundFont(真实音质合成)

用于把 MIDI 合成真实乐器音质的 wav(song_engineer 的 `synthesize_midi_fs.py` / `synth_full_song_fs.py`)。numpy 极简合成音质差,FluidSynth+SoundFont 是推荐路线。

### 1. 下载 FluidSynth

从 GitHub Release 下载 Windows 预编译包:
- 地址:https://github.com/FluidSynth/fluidsynth/releases/tag/v2.5.7
- 文件:`fluidsynth-v2.5.7-win10-x64-cpp11.zip`

解压到(示例):
```
D:\Program Files\fluidsynth-v2.5.7-win10-x64-cpp11\fluidsynth-v2.5.7-win10-x64-cpp11\
```

解压后应包含:
```
bin\fluidsynth.exe
bin\libfluidsynth-3.dll       # pyfluidsynth 需要这个
bin\SDL3.dll
bin\sndfile.dll
include\
lib\
```

> FluidSynth 包本身**不含 SoundFont**,需单独下载(下一步)。

### 2. 下载 SoundFont

在 FluidSynth 目录下建 `sfs\` 文件夹,放入 SoundFont(.sf2/.sf3)文件:

```
D:\Program Files\fluidsynth-v2.5.7-win10-x64-cpp11\fluidsynth-v2.5.7-win10-x64-cpp11\sfs\
├── GeneralUser GS v1.471.sf2      # 推荐,32MB,全乐器,轻量
├── FluidR3_GM2-2.SF2             # 可选,148MB,更饱满
├── Arachno_SoundFont_Version_1.0.sf2  # 可选
└── ...
```

**推荐 GeneralUser GS**(开源、轻量、覆盖 GM 全乐器,吉他/钢琴/人声 Oohs 都有)。下载地址搜 "GeneralUser GS soundfont"。

### 3. 安装 pyfluidsynth(Python 绑定)

```bash
.venv/python.exe -m pip install pyfluidsynth -i https://mirrors.aliyun.com/pypi/simple/
```

> **注意**:有两个同名竞争包 `pyfluidsynth`(1.4.0,带 Synth 类)和 `fluidsynth`(0.2,原始 ctypes 绑定,无 Synth 类)。**只装 pyfluidsynth**。若误装了 `fluidsynth` 0.2,卸载:
> ```bash
> .venv/python.exe -m pip uninstall fluidsynth -y
> ```

### 4. 配置 .env

在项目根目录创建 `.env`:

```
fluidsynth_path=D:\Program Files\fluidsynth-v2.5.7-win10-x64-cpp11\fluidsynth-v2.5.7-win10-x64-cpp11
soundfonts_path=D:\Program Files\fluidsynth-v2.5.7-win10-x64-cpp11\fluidsynth-v2.5.7-win10-x64-cpp11\sfs
```

合成脚本(`synthesize_midi_fs.py` / `synth_full_song_fs.py`)会自动读 `.env`,把 `bin\` 加到 PATH(让 pyfluidsynth 找到 libfluidsynth-3.dll),并在 `soundfonts_path` 找 SoundFont(默认用 GeneralUser GS)。

### 5. 验证 FluidSynth 合成

```bash
# 合成一个测试 wav(钢琴 C-E-G 和弦)
.venv/python.exe -c "
import os
env = {}
with open('.env', encoding='utf-8') as f:
    for l in f:
        if '=' in l: k,v=l.strip().split('=',1); env[k]=v
os.environ['PATH'] = os.path.join(env['fluidsynth_path'],'bin') + ';' + os.environ['PATH']
import fluidsynth, numpy as np, soundfile as sf
sf_dir = env['soundfonts_path']
sf_file = next(os.path.join(sf_dir,f) for f in os.listdir(sf_dir) if 'GeneralUser' in f)
fs = fluidsynth.Synth(samplerate=44100, gain=0.8)
sfid = fs.sfload(sf_file); fs.program_select(0, sfid, 0, 0)
fs.noteon(0,60,100); fs.noteon(0,64,100); fs.noteon(0,67,100)
s = fs.get_samples(44100); fs.noteoff(0,60); fs.noteoff(0,64); fs.noteoff(0,67)
s = np.append(s, fs.get_samples(44100)).astype(np.float32).reshape(-1,2).mean(1)
sf.write('_test.wav', s/np.max(np.abs(s))*0.9, 44100)
print('OK, 有声' if np.max(np.abs(s))>100 else '静音,检查SF')
"
```

输出 `OK, 有声` 即成功。播放 `_test.wav` 应听到钢琴和弦。

---

## 七、其他技能依赖

### song_engineer(工程聚合+合成)
依赖 mido + soundfile + numpy(已在第四节装),无需额外。

### ai_chords_master / muse-lyrics-gen / muse_ai_master(生成技能)
纯文本生成,无需 Python 库,依赖 LLM(AI 对话时调用)。

### minimax-music-* (MiniMax 生成)
- `minimax-music-gen` / `minimax-music-api`:依赖 `mmx` CLI(需单独安装,见技能 SKILL.md)
- `minimax-music-web` / `minimax_music_v3`:网页端,无需本地依赖

---

## 八、验证全部就绪

```bash
# 1. 音频库
.venv/python.exe -c "import librosa, soundfile, mido, numpy, scipy; print('音频库 OK')"

# 2. basic_pitch
.venv/python.exe -c "from basic_pitch.inference import predict; print('basic_pitch OK')"

# 3. FluidSynth(读 .env)
.venv/python.exe -c "
import os
env={}
with open('.env',encoding='utf-8') as f:
    for l in f:
        if '=' in l: k,v=l.strip().split('=',1); env[k]=v
os.environ['PATH']=os.path.join(env['fluidsynth_path'],'bin')+';'+os.environ['PATH']
import fluidsynth; fluidsynth.Synth(); print('FluidSynth OK')
"

# 4. 端到端:合成"走在"全曲
.venv/python.exe .workbuddy/skills/song_engineer/scripts/synth_full_song_fs.py
# -> workspace/project/走在/song_engineer/track/full_song_fs.wav (3:06)
```

全通过则环境完整。

---

## 九、已知坑与排查

### 1. absl-py / audioread 残包(导致 TF/librosa 崩)
**症状**:`cannot import name 'flags' from 'absl'` 或 `audioread has no attribute 'available_backends'`。
**原因**:某些包(如 crepe)手动安装时留下无版本元数据的残包。
**修复**:
```bash
.venv/python.exe -m pip install --ignore-installed --no-deps absl-py audioread -i https://mirrors.aliyun.com/pypi/simple/
```

### 2. TensorFlow 链路损坏
**症状**:TF 导入报 `enum_type_wrapper` 等 protobuf 错误。
**处理**:本项目**不用 TF**,basic_pitch 走 onnxruntime 后端绕开。不要试图修 TF。

### 3. pyfluidsynth 找不到 dll
**症状**:`Couldn't find the FluidSynth library`。
**修复**:确认 `.env` 的 `fluidsynth_path` 指向含 `bin\libfluidsynth-3.dll` 的目录。脚本会自动把 bin 加到 PATH。

### 4. fluidsynth 包与 pyfluidsynth 冲突
**症状**:`module 'fluidsynth' has no attribute 'Synth'`。
**原因**:装了 `fluidsynth` 0.2(原始 ctypes 绑定),覆盖了 `pyfluidsynth`。
**修复**:`.venv/python.exe -m pip uninstall fluidsynth -y`,只保留 pyfluidsynth。

### 5. demucs 首次运行慢
首次会下载 HTDemucs 模型(~80MB),之后缓存。CPU 推理 3 分钟音频约需 1-2 分钟。

### 6. MIDI 合成人声听不到歌词
**正常现象**:SoundFont 无人声歌词合成(TTS/Vocaloid 范畴)。program 85(Voice Oohs)只能发"喔"声旋律。要真人声需用 Muse AI/MiniMax 在线生成。

### 7. 中文路径编码
**症状**:Python 脚本读中文路径(如"沙发小曲")报乱码 FileNotFoundError。
**修复**:运行时设 `PYTHONUTF8=1`:
```bash
PYTHONUTF8=1 .venv/python.exe <script.py>
```
合成脚本内部已用 glob 规避,但调用时建议加 `PYTHONUTF8=1`。

---

## 十、版本快照(验证通过)

以下版本组合已在本项目验证通过(2026-07):

| 组件 | 版本 |
|------|------|
| Python | 3.11.15 |
| librosa | 0.11.0 |
| soundfile | 0.14.0 |
| mido | 1.3.3 |
| numpy | 1.26.4 |
| scipy | 1.17.1 |
| basic-pitch | 0.4.0 |
| onnxruntime | 1.28.0 |
| pyfluidsynth | 1.4.0 |
| pretty-midi | 0.2.11 |
| demucs | 4.1.0 |
| absl-py | 2.5.0 |
| audioread | 3.1.0 |
| FluidSynth | 2.5.7 |
| SoundFont | GeneralUser GS v1.471 |

---

## 十一、快速重装(一键脚本)

若环境损坏需重装,在项目根执行:

```bash
# 删旧 venv
rm -rf .venv

# 重建 + 装所有依赖
python -m venv .venv
.venv/python.exe -m pip install --upgrade pip -i https://mirrors.aliyun.com/pypi/simple/
.venv/python.exe -m pip install \
  librosa soundfile mido numpy scipy basic-pitch onnxruntime pyfluidsynth pretty-midi \
  -i https://mirrors.aliyun.com/pypi/simple/
# 修复残包
.venv/python.exe -m pip install --ignore-installed --no-deps absl-py audioread -i https://mirrors.aliyun.com/pypi/simple/
# demucs(可选)
.venv/python.exe -m pip install demucs -i https://mirrors.aliyun.com/pypi/simple/
```

FluidSynth + SoundFont 需手动下载配置(见第六节),无法脚本化。