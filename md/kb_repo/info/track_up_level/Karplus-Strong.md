# Karplus-Strong 合成器

## 原理

Karplus-Strong 是一种**物理建模合成算法**，用于模拟拨弦乐器（如吉他、钢琴、班卓琴）的声音。

### 核心算法

```
1. 初始化：创建一个长度 = 采样率/频率 的缓冲区
           用白噪声填充（模拟拨弦的初始冲击）

2. 循环输出：
   - 读取当前位置的值
   - 计算当前位置和下一个位置的平均值
   - 乘以衰减系数（模拟阻尼）
   - 写入缓冲区
   - 输出当前值
```

### 数学表达

```
y[n] = damping × (y[n-N] + y[n-N+1]) / 2

其中：
- N = 缓冲区长度（周期）= SAMPLE_RATE / frequency
- damping = 衰减系数（通常 0.996~0.999）
```

### 为什么能发出声音

1. **周期性**：缓冲区长度 N 对应基频，所以输出是周期信号
2. **谐波**：噪声包含所有频率成分，经过平均滤波后保留下与周期匹配的频率
3. **衰减**：每次平均都乘以小于1的系数，高频成分衰减更快，模拟真实弦振动

---

## 合成过程

### 单音符合成

```python
def karplus_strong(frequency, duration, velocity=0.8):
    sample_rate = 44100
    
    # 1. 计算周期长度
    period = int(sample_rate / frequency)
    
    # 2. 白噪声填充
    buffer = np.random.randn(period) * velocity
    
    # 3. 循环输出
    n_samples = int(duration * sample_rate)
    output = np.zeros(n_samples)
    
    for i in range(n_samples):
        # 平均滤波 + 衰减
        avg = (buffer[i % period] + buffer[(i + 1) % period]) / 2 * 0.997
        buffer[i % period] = avg
        output[i] = buffer[i % period]
    
    return output
```

### 包络处理

真实乐器有**起音-衰减-延音-释放**四个阶段：

```python
t = np.linspace(0, duration, n_samples)
attack = np.minimum(t * 80, 1.0)           # 快速起音
sustain = np.exp(-t * 2.5)                  # 自然衰减
envelope = attack * sustain

output = output * envelope
```

---

## 不同技术的实现

### 1. 勾弦 (Pluck)
```python
# 普通勾弦：标准 Karplus-Strong
note_audio = karplus_strong(freq, duration, velocity, damping=0.997)
```

### 2. 拍弦 (Slap)
```python
# 拍弦：加入噪声成分模拟拇指冲击
buffer = np.concatenate([
    noise * 2,                    # 强冲击
    noise * 0.5                   # 衰减噪声
])
damping = 0.990                   # 更快的衰减
```

### 3. 琶音 (Arpeggio)
```python
# 琶音：短促的拨弦
note_audio = karplus_strong(freq, duration * 0.7, velocity * 0.8, damping=0.994)
```

---

## 吉他多音符叠加

多个音符需要按时间位置叠加到主音频缓冲区：

```python
def add_note_to_audio(audio, note_audio, start_sample):
    """将单音符添加到主音频"""
    end_sample = start_sample + len(note_audio)
    
    if end_sample <= len(audio):
        # 淡入淡出避免杂音
        fade_len = min(int(0.002 * SAMPLE_RATE), len(note_audio) // 4)
        note_audio[:fade_len] *= np.linspace(0, 1, fade_len)
        note_audio[-fade_len:] *= np.linspace(1, 0, fade_len)
        
        # 叠加
        audio[start_sample:end_sample] += note_audio
```

---

## 优缺点

### 优点

| 优点 | 说明 |
|------|------|
| **计算简单** | 不需要神经网络，纯算法，CPU 即可运行 |
| **真实物理感** | 模拟弦振动，声音比正弦波合成更自然 |
| **可控性强** | 每个音符的频率、力度、时长都可以精确控制 |
| **实时生成** | 延迟低，可以实时响应 MIDI 输入 |
| **资源占用低** | 不需要 GPU，不需要大量内存 |

### 缺点

| 缺点 | 说明 |
|------|------|
| **没有表情** | 无法模拟揉弦、推弦、滑音等技巧 |
| **音色单一** | 只有"拨弦"一种初始激励，缺乏力度变化带来的音色变化 |
| **无环境声** | 没有指板噪音、琴体共鸣等细节 |
| **泛音不自然** | 高频泛音衰减过快，不如真实吉他丰富 |
| **无动态响应** | 无法根据"演奏力度"改变音色 |

---

## 与 MusicGen 的对比

| 特性 | Karplus-Strong | MusicGen |
|------|----------------|----------|
| **控制精度** | ✅ 每个音符可精确控制 | ❌ 只接受文本提示词 |
| **音质** | ⚠️ 基础，缺少细节 | ✅ 真实感强 |
| **GPU 需求** | ❌ CPU 即可 | ❌ 需要 GPU |
| **计算量** | 低 | 非常高 |
| **实时性** | ✅ 实时生成 | ❌ 需要预生成 |
| **MIDI 对应** | ✅ 精确对应 | ❌ 无法精确控制音符 |

---

## 适用场景

**Karplus-Strong 适合**：
- 需要精确 MIDI 控制的场景
- CPU 环境，无法使用 GPU
- 快速原型验证
- 背景音乐、节奏吉他等不需要复杂技巧的轨道

**MusicGen 适合**：
- 追求高质量音频
- 不需要精确音符控制
- 有 GPU 环境
- 氛围音乐、参考音频生成
