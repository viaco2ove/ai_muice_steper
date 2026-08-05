# 乐器音轨生成策略
[track_up_level.md](track_up_level.md)
- FluidSynth 的简单生成的是sf2 音色。特点极度塑料。

- 使用 dawdreamer + Ample Guitar M Lite 等 VST3
音色提高而且能使用一些乐器技巧不再是塑料音色，可以达到daw 差不多的效果
需要下载vst3 音色，而且ai 貌似不太知道技巧键位怎么用。
类似的
  - SFZ 开源音色引擎 + sfizz（开源 C++/VST3 引擎）
- karplus-strong 类
使用 **Karplus-Strong 等进行物理建模*
感觉有点像生成正弦波电信号而已。
12_泛音环境点缀 这个音轨可以试试
- daw
略，没啥好说的。
- ai 黑盒生成
略，没啥好说的。
什么musicgen,suno,minimax-music. 巴拉巴拉巴拉
- 文本格式乐谱工具
guitar pro ,musescore
音色提示有效，乐器技巧缺少或者生硬。

- 环境音色
粉红噪音算法生成 或 免版权素材库（Freesound API）
下载loop
方案 A（纯代码算法生成 - 最轻量）：
使用 Python 的 numpy 生成粉红噪音（Pink Noise）或棕色噪音（Brown Noise）（比普通白噪音更沉闷自然，像远处的雨声），再添加极慢的幅度调制（LFO）模拟雨势起伏，自动裁切至整曲长度。

方案 B（API 动态下载）：
在 Python 构建脚本中调用 freesound-python API，根据 Tag "soft rain ambient loop" 自动下载一段高清雨声 .wav 循环平铺。

- 真正的ai 乐器音轨生成
  - ace studio 啥的 很贵。有没有更靠谱的免费或者低价的技术
  - Google DDSP 是一种使用深度学习生成音乐的工具。可微分数字信号处理。
  - RAVE 依赖原始输入音轨
  - ACE-Step 这是ACE Studio团队联合开源的音乐生成基础模型

# 例子
在这份混音配置文件中，标识为 `"source": "auto"` 的音轨代表需要通过自动化程序或 AI 算法在后台**动态生成**波形文件。

结合歌曲参数（BPM 68、沙发小曲/Chill 风格）以及各个音轨的音量与备注（如 Pad 和白噪音音量仅为 `0.01`），除去已经用 Dawdreamer + Ample 渲染的吉他和贝斯外，其余 `"auto"` 音轨的具体生成策略与技术选型如下：

---

### 一、 歌声类音轨（02_主唱 & 09_和声）

#### 1. `02_主唱`（Main Vocal）



* **生成技术**：**DiffSingerMiniEngine** 或 **OpenUTAU / SVS 自动化 CLI**。
* **输入依赖**：需要预先准备 `02_主唱.midi`（主旋律乐谱）和 `lyrics.txt`（歌词文件）。
* **自动化生成流程**：
1. 调用 `DiffSingerMiniEngine` 加载适合治愈/民谣/Lo-Fi 风格的开源声库（如某些温暖女声或男低音声库）。
2. 传入 68 BPM 的节奏与乐谱数据，渲染出纯净的主唱人声 `.wav`。


3. **自动化 post-processing**：脚本自动应用全局 gain 控制（配置文件中已指定 `gain_db: 6.0` 放大主唱）。





#### 2. `09_和声`（Backing Vocal / Harmony）



* **生成技术**：**乐理算法自动生成 MIDI + DiffSinger 渲染** 或 **主唱音频 Pitch-Shift**。
* **自动化生成方案（二选一）**：
* **方案 A（AI 生成三/五度和声 - 推荐）**：
编写 Python 脚本解析主唱 MIDI，根据歌曲调式（JSON 中提到的是 Eb 调/C 调编排）自动生成比主旋律高/低三度或五度的和声 MIDI 轨，传入 DiffSinger（可适当调高 Formant 改变音色），生成独立和声音频。
* **方案 B（音频 DSP 算法重采样）**：
直接将生成的 `02_主唱.wav` 输入 Python 音频处理库（如 `librosa` 或 `pydub`），进行三度音高微调（Pitch Shift）与低通滤波（Low-pass filter），再通过配置里的 `vol: 0.1` 混合到背景中。





---

### 二、 铺底与环境音轨（10_氛围垫音pad & 11_自然白噪音）

这类音轨在配置文件中 `vol` 被设为极低的 `0.01`，它们的作用是**提供声音空间感与包裹感（Glue/Texture）**，不需要复杂的乐理，适合程序化或 AI 快速生成。

#### 1. `10_氛围垫音pad`（Ambient Pad）



* **生成技术**：**SoundFont (SFZ) 动态渲染** 或 **纯代码 DSP 合成**。
* **生成方案**：
* **方案 A（SFZ + sfizz/FluidSynth）**：
提取吉他轨的和声走向（Chords），生成一条持续长音（Whole Notes）MIDI 轨，使用带有长 Attack/Release 的 Warm Pad 音色库渲染。
* **方案 B（Python 程序化正弦波/加法合成 - 无依赖）**：
使用 `numpy` 和 `scipy` 根据和弦根音与五音生成多重正弦波，叠加缓入缓出的包络（Envelope），并经过深度低通滤波（Cutoff < 500Hz），生成极为柔和的底层铺底垫音。



#### 2. `11_自然白噪音`（Nature White Noise / 雨声环境）



* **生成技术**：**粉红噪音算法生成** 或 **免版权素材库（Freesound API）自动抓取**。
* **生成方案**：
* **方案 A（纯代码算法生成 - 最轻量）**：
使用 Python 的 `numpy` 生成**粉红噪音（Pink Noise）**或**棕色噪音（Brown Noise）**（比普通白噪音更沉闷自然，像远处的雨声），再添加极慢的幅度调制（LFO）模拟雨势起伏，自动裁切至整曲长度。
* **方案 B（API 动态下载）**：
在 Python 构建脚本中调用 `freesound-python` API，根据 Tag `"soft rain ambient loop"` 自动下载一段高清雨声 `.wav` 循环平铺。



---

### 三、 音效点缀类（12_泛音环境点缀）



#### `12_泛音环境点缀`（Harmonics Accent）



* **生成技术**：**Karplus-Strong 物理建模** 或 **高音区琴线采样**。
* **生成方案**：
* 在小节转换或乐句空隙（如 Intro/Outro）处，根据歌曲主调（Eb/C），随机或按固定逻辑生成 1~2 个高音区八度音符（如 $Eb_5, Bb_5$）。
* 调用轻量化的 **Karplus-Strong 算法**（利用延迟线与低通滤波模拟吉他/风铃高音泛音的天然衰减），生成极具空气感的清脆点缀声，配合混响（Reverb）挂载到混音链中。




### 总结

这种混音架构设计得非常优雅：

1. **核心乐器（吉他/贝斯）**：交由 **Ample Sound VST3 + KeySwitch 编译器** 保证商业级品质。


2. **人声（主唱/和声）**：交由 **DiffSinger (SVS Engine)** 保障唱词和旋律表达。


3. **环境氛围（Pad/白噪音/泛音）**：通过 **DSP 纯代码算法或轻量采样** 在毫秒级内自动合成，以极低音量（`0.01`）混入，实现“沙发音乐（Sofa Chill）”特有的包裹感与治愈氛围。