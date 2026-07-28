# 人声 WAV 转 MIDI 清洗原理

本文档说明 wav_to_midi.py 的 8 步清洗管线每步对应解决什么问题，以及方案选型依据。原理根源见 `md/kb_repo/info/wav_to_mid.md`。

---

## 一、根本矛盾

- **WAV**：连续波形，记录所有颤音/滑音/气声/泛音/混响/呼吸
- **MIDI**：离散音符指令，只有"音高+起止时间"，只认规整方块音符

人声全程是连续滑音颤音，pyin 这类逐帧追踪每 ~23ms 生成一个音高，直接转 MIDI 就是密密麻麻碎音符。这就是 recognize_melody.py 产出 57% 碎音的根因。

---

## 二、方案选型（双后端：basic_pitch 优先 + pyin fallback）

| 方案 | 精度 | 当前环境 | 选型 |
|------|------|---------|------|
| basic_pitch（Spotify 神经网络） | 高（直接学"音符"概念，带velocity起伏） | ✅ 已通过 onnxruntime 救活 | **优先采用** |
| librosa.pyin + 8步清洗 | 中（干净但轮廓被平滑） | ✅ 可用 | fallback |
| crepe（深度学习） | 高 | ❌ 依赖 tensorflow.keras，TF依赖链损坏 | 不可用 |

### 为什么 basic_pitch 优先
basic_pitch 是神经网络，训练时直接学过"什么是音符"，输出的是有语义的音符（带起止、力度），而非逐帧频率。因此：
- 能捕捉人声的细微起伏（pyin 的中值滤波会抹平这些）
- 输出带 velocity（人声力度映射），听感更自然
- 内置 onset/frame 检测，碎音天然少

实测（vocals.wav）：basic_pitch 45音/平均0.268s/带velocity，pyin清洗版 29音/平均0.524s/无力度。basic_pitch 更贴合人声轮廓。

### 为什么保留 pyin 后端
- 不依赖 onnxruntime 时（如迁移到其他环境）仍可用
- basic_pitch 推理较慢（20-60s），pyin 更快
- 极简场景 pyin 够用

### basic_pitch 救活过程（环境修复记录）
basic_pitch 原本因依赖链损坏不可用，修复步骤：
1. 装 onnxruntime（basic_pitch 自带 nmp.onnx 模型，无需 TF 加载）
2. 重装 absl-py（venv 里是残包无版本元数据，用 `pip install --ignore-installed --no-deps absl-py` 覆盖）
3. 重装 audioread（同上残包，缺 available_backends 导致 librosa.load 崩）
4. 修复后 basic_pitch 用 onnx 后端跑通，不碰 TF 那条烂链子

详见 memory/2026-07-27.md。

---

## 三、8 步清洗管线详解

### Step 1：加载
用 `soundfile.read` 而非 `librosa.load`。
- **原因**：librosa 0.11 的默认后端 audioread 有版本兼容问题（`audioread has no attribute available_backends`），soundfile 不受影响。
- 转 mono：多声道取第一声道。

### Step 2：预处理
归一化到 [-1,1] + noise gate。
- **noise gate**：低于 -40dB 的样本置零。
- **解决的问题**（kb 文档第二章3）：呼吸、齿音、底噪会被判为低频/中频音符。gate 把这些静音段先压掉，减少后续误判。

### Step 3：pyin 音高提取
`librosa.pyin(fmin=80, fmax=800, fill_na=nan)`。
- **fmin/fmax 限定人声音域**：默认 80-800Hz 覆盖男声低音到女声高音。超出范围的频率（如低频底噪、高频泛音）直接不提取。
- **fill_na=nan**：无声帧用 nan 而非 0，便于后续区分"无声"和"音高为0"。
- 输出 f0（频率）/ voiced_flag（有声）/ voiced_probs（概率）。

### Step 4：有声帧过滤
`f0[~voiced_flag] = nan`。
- **解决的问题**：旧版把无声帧也处理成 midi=-1 碎片，CSV 里几千行零散数据。本步只保留有声帧，无声段断开（不产生音符）。

### Step 5：中值滤波
`scipy.ndimage.median_filter(window=5)`，对 f0 序列平滑。
- **解决的问题**（kb 文档第一章1）：单帧音高跳变（颤音/瞬态误判）。
- **中值而非均值**：中值滤波保留音高台阶的锐利边界，均值会让音符边界模糊。
- **nan 段不参与**：滤波时 nan 段保持 nan，不污染有声段。

### Step 6：跳变修正
相邻帧音程 > 7 半音且持续 < 3 帧的视为误判，用前值填充。
- **解决的问题**（kb 文档第一章1）：八度跳变、泛音误判。人声不会在 70ms 内跳一个八度又跳回来，这种短时大跳是误判。
- **持久跳变保留**：持续 ≥3 帧的跳变可能是真转音，不修正。
- 返回 midi 序列（-1=无声）。

### Step 7：音符合并
连续相同/相近（±1 半音）的帧合并为一个音符，取段内中位数为代表音高。
- **±1 半音容差**：pyin 对同一音可能有 ±1 半音抖动，视为同一音。
- **取中位数而非首帧**：中位数抗抖动，代表音高更准。
- 记录起止时间（帧号 × hop_sec）。

### Step 8：碎音过滤
丢弃时长 < 80ms 的音符 + 丢弃音域外的音符。
- **80ms 阈值**：人耳能感知的最短音符约 50-80ms，低于此基本是碎音。旧版无此过滤，10ms 碎音都保留。
- **音域过滤**：即使经过前面步骤，偶有低频（呼吸）或高频（泛音）误判漏过，用 fmin/fmax 对应的 midi 范围再卡一次。

---

## 四、参数对应问题速查

| 参数 | 默认 | 对应解决 |
|------|------|---------|
| fmin/fmax | 80/800 | 限定人声音域，过滤底噪/泛音误判 |
| min_note_dur | 0.08s | 过滤碎音（kb第三章核心问题） |
| median_window | 5 | 平滑单帧跳变（颤音/瞬态） |
| max_jump | 7 半音 | 修正八度跳变/泛音误判 |
| merge_tolerance | 1 半音 | 合并同音抖动 |
| noise_gate | -40dB | 压底噪/呼吸（Step2） |

---

## 五、导出细节

- **单轨钢琴音色**（program=0）：通用，任何播放器都能放。
- **力度按时长映射**：短音弱（50）、长音强（95），模拟人声力度起伏，听感更自然。
- **ticks_per_beat=480，按 120BPM 换算时间**：与 recognize_melody.py 一致，便于对比。
- **note_on/note_off 配对**：标准 MIDI，无重叠。