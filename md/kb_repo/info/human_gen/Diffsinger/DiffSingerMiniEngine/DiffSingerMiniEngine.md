DiffSingerMiniEngine 的运行细节与使用说明如下：

---

### 1. 输入什么，生成什么？

* **输入（Inference Inputs）**：
* **乐谱与调音数据**：包含音素序列（Phonemes）、音高/MIDI 频率数据（F0 曲线或 Pitch）以及每个音素的时长（Durations）。
* **ONNX 模型文件**：配置文件所指定的 ONNX 格式声库资产（包含声学模型、节奏/时长模型以及神经网络声码器）。


* **生成（Outputs）**：
* **高清歌声音频**：标准的 WAV 格式音频（通常为 44.1kHz 采样率的纯净人声演唱）。



---

### 2. 是否需要部署“大模型”？

**不需要。**

* **模型规模极小**：DiffSingerMiniEngine 运行的是轻量级 **SVS（歌声合成）专用模型**，而非动辄几 B/几十 B 参数的 LLM 或大语言模型。
* **磁盘与内存占用低**：一套完整包含声码器（如 NSF-HiFiGAN）和声学模型的 ONNX 声库，体积通常在 **100MB ~ 400MB** 之间，参数量仅在千万级左右。

---

### 3. 硬件要求

得益于底层采用 ONNX Runtime 引擎，其硬件开销极低：

* **CPU**：**普通双核 CPU 即可**。无需多核服务器，即可达到接近实时或超实时的渲染速度。
* **内存 (RAM)**：**2GB - 4GB** 即可（模型加载到内存仅占用 200MB ~ 600MB 左右）。
* **显卡 (GPU)**：**非必须**。完全可以使用 CPU 推理；若配置英伟达 GPU（CUDA / DirectML），推理速度会更快，显存占用在 1GB 以内。
* **存储空间**：仅需预留不到 1GB 空间用于代码库和 ONNX 模型权重。

---

### 4. 怎么调用和使用？

#### 准备环境与模型权重

1. **安装依赖**：
```bash
pip install onnxruntime PyYAML soundfile

```


2. **下载/准备 ONNX 模型资产**：
将转换好的 ONNX 格式模型放入对应文件夹：
* `assets/acoustic/`：声学模型 (`.onnx`)
* `assets/vocoder/`：NSF-HiFiGAN 声码器 (`.onnx`)
* `assets/rhythmizer/`：节奏/时长预测器 (`.onnx`)



#### 常见调用方式

**方式 1：服务端 API 调用（HTTP / Server）**
直接启动 Engine 自带的服务端脚本：

```bash
python server.py --config configs/default.yaml

```

启动后，业务服务或前端界面可通过 HTTP 向该端口发送包含音素、音高和时长的 JSON 报文，服务端处理后返回合成的音频流或文件路径。

**方式 2：Python 代码直接调用**
在本地 Python 代码中引入并直接推理：

```python
from synthesis import MiniEngine  # 引擎提供的入口脚本

# 加载配置文件与 ONNX 依赖
engine = MiniEngine("configs/default.yaml")

# 传入音素、音高及时长数组，进行合成
audio_data = engine.synthesize(
    phonemes=["d", "a", "s", "i"],
    pitches=[60, 60, 62, 62],
    durations=[0.2, 0.2, 0.3, 0.3]
)

```

**方式 3：集成至调音前端（如 OpenUTAU）**
将 MiniEngine 打包为可执行引擎程序，并在 OpenUTAU / DiffScope 等调音软件中配置为渲染后端（Render Engine）。调音软件在用户点击播放时，会自动组装参数并调用 MiniEngine 完成后台实时音频渲染。