# MiniMax Music API 控制标签参考

本文档定义 mmx CLI / API 调用时的人声、情绪、编曲控制参数。通过 `--vocals`、`--mood`、`--instruments`、`--genre` 等结构化参数控制音乐生成。

---

## 一、核心参数速查

### --vocals（人声控制）

| 参数值 | 含义 | 适用场景 |
|--------|------|----------|
| `soft male vocals` | 柔和男声 | 民谣/Lo-Fi |
| `whispered male voice` | 男声低语 | 慵懒小曲 |
| `breathy vocals` | 气声 | Interlude |
| `soft female vocals` | 柔和女声 | 流行/民谣 |
| `murmured vocals` | 呢喃人声 | Lo-Fi |
| `low output vocals` | 低输出人声 | 私密感 |
| `monotone delivery` | 平调唱腔 | 疏离感 |
| `emotionless vocals` | 无情绪人声 | 内敛 |
| `nasal vocal tone` | 鼻腔共鸣 | 特定风格 |
| `warm vocal tone` | 温暖人声 | 回忆感 |

### --mood（情绪控制）

| 参数值 | 含义 |
|--------|------|
| `peaceful` | 平静 |
| `melancholic` | 忧郁 |
| `chill` | 慵懒 |
| `dreamy` | 梦幻 |
| `nostalgic` | 怀旧 |
| `lonely` | 孤独 |
| `relaxed` | 放松 |
| `contemplative` | 内省 |
| `detached` | 疏离 |
| `wistful` | 惆怅 |
| `ethereal` | 空灵 |
| `bittersweet` | 苦乐参半 |

### --genre（曲风）

| 参数值 | 含义 |
|--------|------|
| `lo-fi` | Lo-Fi |
| `lo-fi folk` | Lo-Fi民谣 |
| `indie folk` | 独立民谣 |
| `ambient folk` | 氛围民谣 |
| `acoustic folk` | 原声民谣 |
| `chillout` | 弛放 |
| `ambient` | 氛围 |
| `dream pop` | 梦幻流行 |
| `slowcore` | 慢核 |
| `sadcore` | 悲伤核 |
| `chamber folk` | 室内民谣 |
| `acoustic` | 原声 |

### --instruments（乐器）

| 参数值 | 含义 |
|--------|------|
| `acoustic guitar` | 木吉他 |
| `fingerpicking guitar` | 指弹吉他 |
| `clean electric guitar` | 清音电吉他 |
| `piano` | 钢琴 |
| `electric piano` | 电钢琴 |
| `ambient pads` | 氛围垫音 |
| `soft strings` | 轻柔弦乐 |
| `bass` | 贝斯 |
| `light percussion` | 轻柔打击 |
| `hand percussion` | 手击打击 |
| `marimba` | 马林巴 |
| `glockenspiel` | 钢片琴 |

---

## 二、BPM / Tempo 映射

| 情绪/场景 | BPM 范围 | 描述 |
|-----------|----------|------|
| 极度慵懒 | 50-65 | 慢到几乎停止 |
| 沙发小曲 | 65-75 | 缓慢放松 |
| Lo-Fi | 70-85 | Lo-Fi 标准 |
| 民谣中速 | 80-95 | 自然流动 |
| 轻快民谣 | 95-110 | 略带节奏 |
| 标准流行 | 110-130 | 常规节奏 |

---

## 三、组合参数模板

### 3.1 沙发小曲（Lo-Fi Sofa）

```bash
--genre "lo-fi, ambient folk" \
--mood "chill, relaxed, detached" \
--vocals "whispered male voice, low output, emotionless" \
--instruments "fingerpicking guitar, ambient pads" \
--bpm 68
```

### 3.2 慵懒民谣（Lazy Folk）

```bash
--genre "indie folk, acoustic folk" \
--mood "peaceful, nostalgic, contemplative" \
--vocals "soft male vocals, murmured, breathy" \
--instruments "acoustic guitar, light piano" \
--bpm 75
```

### 3.3 氛围空灵（Ambient Ethereal）

```bash
--genre "ambient, dream pop" \
--mood "dreamy, ethereal, wistful" \
--vocals "soft female vocals, breathy, distant" \
--instruments "ambient pads, soft strings, glockenspiel" \
--bpm 60
```

### 3.4 城市孤独（Urban Loneliness）

```bash
--genre "lo-fi, slowcore" \
--mood "lonely, detached, melancholic" \
--vocals "low output vocals, monotone delivery" \
--instruments "electric piano, light bass, ambient pads" \
--bpm 65
```

---

## 四、--avoid 参数（禁用元素）

| 禁用参数 | 效果 |
|----------|------|
| `--avoid drums` | 无鼓组 |
| `--avoid bass` | 无重贝斯 |
| `--avoid electronic` | 无电音 |
| `--avoid build-up` | 无高潮爆发 |
| `--avoid percussion` | 无打击乐 |
| `--avoid loud vocals` | 无大音量人声 |

示例：
```bash
--avoid drums --avoid electronic --avoid build-up
```

---

## 五、--use-case 参数

| 参数值 | 含义 |
|--------|------|
| `background music` | 背景音乐 |
| `meditation music` | 冥想音乐 |
| `study music` | 学习音乐 |
| `sleep music` | 睡眠音乐 |
| `coffee shop ambiance` | 咖啡店氛围 |
| `rainy day atmosphere` | 雨天氛围 |

---

## 六、Prompt 英文模板

API prompt 应使用英文，以下是常用模板：

```
A [mood] [genre] song, featuring [vocals description],
with [instruments], [tempo description], [atmosphere].
[--avoid ...]
```

示例：
```
A chill lo-fi folk song, featuring whispered male vocals with low output,
with fingerpicking guitar and ambient pads, slow and relaxed atmosphere.
No drums, no electronic sounds, no build-up.
```

---

## 七、中英文对照速查

| 中文 | English |
|------|---------|
| 无鼓组 | no drums |
| 慵懒 | chill, lazy |
| 呢喃 | murmur, whisper |
| 气声 | breathy |
| 留白 | space, minimal |
| 疏离 | detached, distant |
| 内省 | contemplative, introspective |
| 迷茫 | lost, wandering |
| 平静 | peaceful, calm |
| 温暖 | warm |
| 极简 | minimalist |
| 爆发 | build-up, climax |
