要让 DiffSinger 唱出自然、流畅且带有转音/哼唱的歌声，歌词格式、MIDI 音符对齐以及 F0（音高曲线）的处理需要遵循以下规范：

---

### 一、 歌词的标准格式与 MIDI 对应法则

#### 1. 对应原则：**线性一对一对齐**

MIDI 中的音符是**按时间（Tick）从前往后排列**的。歌词匹配的黄金法则是：**1 个 MIDI 音符 = 1 个汉字（或休止符/连音符）**。

#### 2. 特殊符号定义

| 符号 | 含义 | 说明 |
| --- | --- | --- |
| **汉字/拼音** | 普通发音 | 如 `门`、`风` 或 `men`、`feng`，占用 1 个音符的时值。 |
| **`R` / `SP` / `sil**` | 休止符（静音） | 代表无声、停顿或吸气。无声小节必须对应 `R`。 |
| **`-`（减号）** | **连音符 / 转音符** | **最核心符号！** 表示延续上一个字的元音（一字多音/转音）。 |

#### 3. 对应示例（MIDI 与歌词对齐表）

假设一段旋律有 6 个 MIDI 音符：

| 音符顺序 | MIDI 音高 | 对应歌词 | 实际唱法说明 |
| --- | --- | --- | --- |
| 音符 1 | C4 | **门** | 唱 `men` |
| 音符 2 | - | **R** | 停顿/休止 |
| 音符 3 | E4 | **风** | 唱 `feng`（开始转音） |
| 音符 4 | G4 | **-** | 继续唱 `feng` 的韵母 `eng`，但音高滑升到 G4 |
| 音符 5 | F4 | **-** | 继续唱 `feng` 的韵母 `eng`，音高降到 F4 |
| 音符 6 | D4 | **虚** | 唱 `xu` |

> **提示**：`风 -> - -> -` 这三个连续音符组合在一起，就构成了自然的**一字多音（转音/颤音）**。

---

### 二、 哼唱（Humming）的处理方法

在歌词中有许多无实义的衬字或哼唱（如“嗯…”、“啊…”、“呜…”），DiffSinger 的处理方式如下：

#### 1. 常见哼唱字的拼音与音素映射

只需要在歌词文本中使用对应的汉字或拼音即可，字典（`dictionary.txt`）会自动解析：

* **闭嘴哼鸣（`M` / `N` 音）**：
* 歌词写：`嗯` 或 `m`、`ng`
* 拼音解析：`ng` 或 `en`
* 效果：发闭唇或鼻音哼唱。


* **开口哼唱（`A` / `O` / `U` 音）**：
* 歌词写：`啊`（`a`）、`噢`（`o`）、`呜`（`wu`）
* 效果：发出开朗的吟唱或垫音。



#### 2. 哼唱的长音/转音

如果哼唱需要跨越多个音高（如“嗯~~~”从 C4 滑到 G4）：

* **MIDI 安排**：放置连续的 3 个音符（C4 -> E4 -> G4）。
* **歌词安排**：`嗯` -> `-` -> `-`。

---

### 三、 滑音与转音（Portamento & Slur）的代码层处理

代码中不能直接把音高硬切成阶梯状，需要从**音素分配**和 **F0 平滑**两方面进行修复：

#### 1. 音素分配：处理 `-`（连音符）

当遇到 `-` 时，**不提取新字的声母**，直接继承上一个字的**韵母**，并将模型的 `is_slur` 张量标记为 `1`：

```python
# 逻辑示意：
last_fin = 'a' # 上一个字的韵母
for ly in lyrics:
    if ly == '-':
        # 连音/转音：保持上一个字的韵母，is_slur 设为 1
        tokens.append(p2id[last_fin])
        is_slurs.append(1)
    elif ly in ('R', 'SP'):
        tokens.append(p2id['SP'])
        is_slurs.append(0)
    else:
        # 新字：正常提取声母+韵母
        ini, fin = _split_pinyin(ly)
        last_fin = fin
        tokens.append(p2id[fin])
        is_slurs.append(0)

```

#### 2. F0（音高曲线）平滑过度（解决硬切变声）

原代码在音符交界处是硬切换的（上一帧 C4，下一帧立刻变 G4），听起来像机器人。需要加入 20ms~50ms 的**平滑过渡（平滑插值）**：

```python
# F0 过渡平滑处理（避免音高阶梯硬切换导致的电音怪异感）
def smooth_f0(f0_array, window_size=5):
    """使用滑动平均对 F0 阶梯曲线进行平滑，实现自然滑音"""
    kernel = np.ones(window_size) / window_size
    smoothed = np.convolve(f0_array[0], kernel, mode='same')
    return smoothed.reshape(1, -1)

```

---

### 四、 标准对齐脚本（修改后的逻辑简化）

要彻底解决歌词乱序问题，请弃用 `bar_segs` 按小节截取的旧代码，改为**按 MIDI 音符顺序线性分配**：

```python
def align_lyrics_linearly(midi_notes, lyrics_text):
    """
    按时间顺序，1个MIDI音符精准匹配1个字符
    """
    # 提取 lyrics_clean.txt 中所有的有效字符（含汉字、…、-、R）
    clean_chars = []
    for char in lyrics_text:
        if '一' <= char <= '鿿' or char in ('-', 'R', '…'):
            clean_chars.append(char)
            
    matched_lyrics = []
    char_idx = 0
    total_chars = len(clean_chars)
    
    for note in midi_notes:
        if char_idx < total_chars:
            matched_lyrics.append(clean_chars[char_idx])
            char_idx += 1
        else:
            matched_lyrics.append('R') # 歌词不够时用休止符填补
            
    return matched_lyrics

```

按照此逻辑：

1. MIDI 中的每一个音符都有对应的汉字或 `-`。
2. 配合字典中的 `声母 + 韵母` 输出，咬字会变得极其清晰。
3. 遇到带有 `-` 的音符时，音高会自然平滑滑动，实现逼真的**滑音与转音**效果。