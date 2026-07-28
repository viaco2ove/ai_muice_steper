---
name: muse_ai_master
description: 创建 Muse AI 大师模式歌词结构和生成歌曲。用于用户想要用 Muse AI 生成歌曲、需要设计歌词段落结构、选择音乐风格时触发。包含完整的歌词结构标签、格式规范、风格推荐和示例模板。
agent_created: true
---

# Muse AI 大师模式歌词创作技能

## Overview

本技能帮助用户为 Muse AI (https://muse.top/) 大师模式创建高质量歌词。通过掌握歌词结构标签、格式规范和风格选择，生成符合 Muse AI 期望的专业级歌曲。

## 输出
[muse_ai](../../../workspace/muse_ai)/{song_name}/

## 工作模式

本技能支持两种工作模式，默认使用**编曲模式**：

### 编曲模式（默认）

适用场景：已有编曲方案、和弦骨架、风格定位，需要Muse AI 精准还原。

核心特征：在歌词文件顶部写完整的**【全局设定】区块**，包含风格/BPM/人声要求/核心配器/禁用元素/和弦进行/文化底色，让Muse AI 从编曲层面就开始约束生成。

参考格式：见 [岛屿低语者](muse_ai/Whisper%20of%20the%20Isle(岛屿低语者).md) 的【全局设定】段落——这是编曲模式的标准模板。

**【全局设定】必填字段**：

| 字段 | 说明 | 示例 |
|------|------|------|
| 曲风 | 具体曲风+拍号+核心特征 | Lo-Fi 沙发小曲，4/4拍，无鼓组 |
| BPM | 精确数值 | 68 |
| 人声 | 性别/质感/唱法要求 | 男声低输出呢喃，松弛慵懒 |
| 核心配器 | 主要乐器+Capo/调式信息 | 木吉他分解和弦（Capo 3，C 调指法，实际音高 Eb） |
| 禁用 | 明确不要什么 | 鼓组、重贝斯、电音、副歌爆发 |
| 和弦骨架 | 基础和弦进行 | C7 C7 \| Em7/B Em7/B \| C7 C7 \| Em7/B Em7/B \| Em7 |
| 文化底色 | 风格/情绪/主题方向 | 身体与灵魂的分裂漫游，随时随地进入别处，不抵达 |

### 段落模式

适用场景：只需要设计歌词段落结构，不涉及具体编曲约束。

核心特征：在歌词文件顶部写**风格标签**（如 `[Lo-Fi]` `[民谣]`）和**语种/情绪标签**（如 `[普通话]` `[Adagio]`），不写【全局设定】区块。

参考格式：

```
风格标签：`[Lo-Fi]` `[民谣]` `[Indie Pop]`
语种：`[普通话]`
情绪：`[Adagio]` `[Legato]` `[Dolce]`
```

## 默认模式说明

除非用户明确说"只需要段落结构"或"段落模式"，否则一律走**编曲模式**——这是默认行为。

## 核心规则

### 1. 歌词基本格式

- **每段 4 行左右**：AI 演唱效果最理想，过长歌词会导致部分内容被忽略
- **每句独立一行**：合理换行，每句歌词单独一行
- **行尾不加标点**：句尾不建议添加任何标点符号
- **行内可加分隔符**：行中间可以使用逗号等分隔符

### 2. 歌词结构标签

标签放在段落开头，用方括号包裹，AI 会识别为结构标记而非歌词：

| 中文标签 | 英文标签 | 作用说明 |
|---------|---------|---------|
| `[前奏]` / `[Intro]` | `[Intro]` | 开场instrumental部分，无歌词 |
| `[主歌]` / `[Verse]` | `[Verse 1]` `[Verse 2]` | 核心叙事部分，推进故事发展 |
| `[预副歌]` / `[Pre-Chorus]` | `[Pre-Chorus]` | 连接主歌和副歌，抬升情绪 |
| `[副歌]` / `[Chorus]` | `[Chorus]` | 歌曲高潮，最具记忆点 |
| `[后副歌]` / `[Post-Chorus]` | `[Post-Chorus]` | 副歌后的延伸和强化 |
| `[桥段]` / `[Bridge]` | `[Bridge]` | 制造变化，可换视角或转调 |
| `[间奏]` / `[Interlude]` | `[Interlude]` | 纯器乐过渡段 |
| `[尾奏]` / `[Outro]` | `[Outro]` | 收尾段落 |

### 3. 人声控制标签

| 标签 | 说明 |
|-----|------|
| `[Male Vocal]` | 男声段落 |
| `[Female Vocal]` | 女声段落 |
| `[Duet]` | 对唱 |
| `[Harmony]` | 和声 |
| `[Rap]` | 说唱段落 |
| `[Whisper]` | 耳语效果 |
| `[Spoken Word]` | 念白 |

### 4. 音乐风格标签

可在歌词中使用音乐术语标签来影响演唱效果：

| 标签 | 说明 |
|-----|------|
| `[a cappella]` | 无伴奏清唱 |
| `[dolce]` | 柔美甜蜜 |
| `[agitato]` | 激动紧张 |
| `[legato]` | 连音流畅 |
| `[staccato]` | 断音短促 |
| `[crescendo]` | 渐强 |
| `[ritardando]` | 渐慢 |
| `[fortissimo]` | 最强音 |
| `[piano]` | 轻柔弱音 |

### 5. 语种控制

| 标签 | 说明 |
|-----|------|
| `[普通话]` / `[Mandarin]` | 强制普通话演唱 |
| `[粤语]` / `[Cantonese]` | 粤语歌曲 |
| `[English]` | 英文歌曲 |

## 常用歌曲结构模板

### 流行歌曲结构 (最常见)
```
[Intro]
[Verse 1]
[Pre-Chorus]
[Chorus]
[Verse 2]
[Pre-Chorus]
[Chorus]
[Bridge]
[Chorus]
[Outro]
```

### 民谣结构
```
[Intro]
[Verse 1]
[Verse 2]
[Chorus]
[Verse 3]
[Chorus]
[Bridge]
[Chorus]
[Outro]
```

### 电子/舞曲结构
```
[Intro]
[Verse 1]
[Build-Up]
[Chorus/Drop]
[Verse 2]
[Build-Up]
[Chorus/Drop]
[Break]
[Build-Up]
[Chorus/Drop]
[Outro]
```

### 说唱结构
```
[Intro]
[Verse 1]
[Hook/Chorus]
[Verse 2]
[Hook/Chorus]
[Verse 3]
[Hook/Chorus]
[Outro]
```

## 创作工作流

1. **确定主题和情绪**：明确歌曲要表达的核心情感和故事
2. **选择歌曲结构**：根据风格选择合适的结构模板
3. **编写歌词内容**：
   - 主歌：叙事铺垫，4-8行
   - 预副歌：情绪抬升，2-4行
   - 副歌：记忆点强，4-8行，可重复
   - 桥段：转折变化，2-4行
4. **添加结构标签**：在每个段落前添加对应标签
5. **丰富演唱效果**：添加语气词(啦~、啊~、嘿)和人声控制标签

## 增强演唱效果的技巧

1. **语气词**：在提示语中添加"嘿"、"啦~"、"啊~"等无意义音节丰富效果
2. **多音字处理**：使用拼音或同音字替代多音字和复杂字
3. **段落留白**：副歌等段落之间额外留一行空白
4. **风格强调**：在开头添加风格标签如`[流行]`、`[民谣]`、`[电子]`

## 示例歌词

### 中文流行歌曲示例
```
[Intro]
[Verse 1]
晨光穿过窗帘洒在桌上
咖啡香气弥漫整个房间
翻看照片里的旧时光
回忆像潮水涌上心房
[Pre-Chorus]
那些年我们一起走过的路
如今只剩我一个人回顾
[Chorus]
如果时光能倒流
我想回到那个夏天
和你再看一次日落
直到星星布满天
[Verse 2]
城市的霓虹依然闪烁
只是身边少了一个你
习惯性的转身想牵手
才发现只剩下影子
[Pre-Chorus]
也许这就是成长的代价
学会了告别学会了放下
[Chorus]
如果时光能倒流
我想回到那个夏天
和你再看一次日落
直到星星布满天
[Bridge]
啊~ 时光啊时光
能否再给我一次机会
[Outro]
直到星星布满天
直到永远
```

### 英文电子舞曲示例
```
[Intro]
[Verse 1]
Walking through the city lights
Everything feels so alive
People rushing everywhere
But I'm just standing there
[Build-Up]
Can you feel it in the air
Something's happening tonight
[Chorus/Drop]
Let it go, let it flow
Dance under the neon glow
We are electric tonight
Feel the music, feel the light
[Break]
(Instrumental break)
[Build-Up]
Rise up, take control
This is where the story unfolds
[Chorus/Drop]
Let it go, let it flow
Dance under the neon glow
We are electric tonight
Feel the music, feel the light
[Outro]
Electric tonight
Feel the light
```

## 注意事项

1. 标签大小写要一致，统一使用英文标签或中文标签
2. 不要混用大小写(如`[Verse 1]`和`[verse 2]`混用)
3. 避免段落过多导致歌曲结构混乱
4. 副歌是最重要的部分，要写得朗朗上口、可重复
5. Muse AI 的分段功能可辅助自动分段，建议分段后再补充标签

## 资源

### references/

- `lyric_structure.md` - 完整的歌词结构标签参考表
- `style_tags.md` - 音乐风格和表情术语标签完整列表
- `templates.md` - 各类型歌曲的结构模板集合
