---
name: minimax_music_v3
description: 将歌词转换为 MiniMax Music 3 网页端可识别的格式。读取 muse_ai 项目的 lyrics.md 和 lyrics.design.md，输出带结构标签和编曲说明的纯文本歌词 + 风格描述，用于粘贴到 https://www.minimaxi.com/audio/music 网页端生成音乐。触发词：MiniMax 音乐生成、music v3、转换歌词格式、生成 MiniMax 歌词。
agent_created: true
---

# MiniMax Music v3 歌词格式化

## Overview

将 muse_ai 项目的歌词转换为 MiniMax Music 3 网页端可识别的格式。MiniMax Music 3 支持 `[Intro]`、`[Verse]`、`[Chorus]` 等结构标签，并允许在标签后补充编曲、人声、情绪说明。

线上文档：
https://vrfi1sk8a0.feishu.cn/wiki/LLjuwJhoMiUGwdkO8k1cB0mFnNc

## 段落控制标签参考

生成歌词时，每个段落都需要在 `[结构标签]` 后紧跟一行 **编曲说明**，用 `[...]` 包裹。
详细标签体系见：[references/control_tags.md](references/control_tags.md)

核心控制维度：
- **编曲**：吉他分解/扫弦、钢琴、氛围垫音、转位和弦
- **人声**：低输出呢喃、气声、音区上下移
- **情绪**：平静慵懒、迷茫内省、疏离
- **节奏**：轻柔留白、无鼓组、禁止爆发

## 模式选择
默认为风格编曲 模式
- 简单模式：[demo1.md](references/demo1.md)
- 歌词编曲：[歌词编曲](references/%E6%AD%8C%E8%AF%8D%E7%BC%96%E6%9B%B2)
- 风格编曲：[风格编曲](references/%E9%A3%8E%E6%A0%BC%E7%BC%96%E6%9B%B2)


## Workflow

### Step 1: 读取源文件

读取项目的歌词文件和设计文件：
```
<project>/muse_ai/<歌名>/lyrics/lyrics.md      # 歌词内容
<project>/muse_ai/<歌名>/lyrics/lyrics.design.md # 风格设定
```

提取关键信息：
- 歌词正文（各段落的歌词行）
- 编曲说明（括号内的制作提示）
- 风格设定（曲风、BPM、配器、禁用项）
- 结构标签（[Intro]、[Verse]、[Chorus] 等）

### Step 2: 格式化歌词

MiniMax Music 3 歌词格式规则：

1. **结构标签**：使用 `[Intro]`、`[Verse]`、`[Pre Chorus]`、`[Chorus]`、`[Interlude]`、`[Bridge]`、`[Outro]` 等标签，独占一行
2. **编曲说明**：用 **方括号 `[...]`** 包裹，放在结构标签后的下一行，独占一行。这是 MiniMax 识别编曲提示的格式
3. **歌词行**：每行一句，编曲说明之后开始
4. **段落分隔**：每个段落之间用空行隔开
5. **气声/呢喃**：用 `…` 前缀表示极轻的气声
6. **段落尾编曲**：段落最后可追加一行 `[编曲说明]` 描述过渡或收尾
7. **字符限制**：歌词字段最多 3500 字符

### 格式模板

```
[Section Tag]
[编曲说明：乐器、节奏、人声、氛围等]
歌词第一行
歌词第二行
...

[Next Section Tag]
[编曲说明]
歌词...
```

### 示例

```
[Intro]
[吉他分解和弦轻柔开场，木吉他单音泛音余韵，极淡氛围垫音，无歌词]

[Verse 1]
[吉他Cadd9到C7sus4分解节奏型，轻柔留白，人声低输出呢喃，无鼓组]
门虚掩着
风掀了快递
```

### Step 3: 格式化风格描述

MiniMax Music 3 风格字段规则：
- 最多 2000 字符
- 描述曲风、情绪、配器、人声特征
- 用英文+中文混合描述效果更好
- 明确标注禁用元素（如 no drums, no bass）

### Step 4: 输出文件

输出到 `<project>/workspace/minimax_music_v3/`：
- `lyrics_<歌名>.txt` — 纯文本歌词（粘贴到歌词框）
- `style_<歌名>.txt` — 风格描述（粘贴到风格框）
- `README.md` — 使用说明（包含网页端操作步骤）

## MiniMax Music 3 支持的结构标签

```
[Intro] [Verse] [Pre Chorus] [Chorus] [Interlude]
[Bridge] [Outro] [Post Chorus] [Transition]
[Break] [Hook] [Build Up] [Inst] [Solo]
```

- 歌曲结构：输入斜杠/后，可以查看我们支持的14种歌词结构，点击对应的关键词即可插入。
14种歌词结构：前奏（Intro）、主歌（Verse）、预副歌（Pre-chorus）、副歌（Chorus）、Hook（Hook）、Drop（Drop）、过门（Bridge）、Solo（Solo）、递进（Build-up）、器乐段（Instrumental）、BreakDown（Breakdown）、间歇段（Break）、间奏（Interlude）、尾奏（Outro）
👇举个例子：
```
[intro]

[verse]
My heart is beating like a drum
I feel it in my soul
Oh my love
Finally the world is whole

[chorus]
I see the light
I feel the heat
Everything is dancing
In the middle of the street
I see the clouds
I feel the air
Love is everywhere

[verse]
The sky is bright and blue today
The trees are standing tall
Everything is moving
No more shadows on the wall

[bridge]
I see the truth
I feel the dream
Everything is clear
Like a mountain stream

[outro]
```
例子库
[references](references)
- 歌词里编曲：[歌词编曲](references/%E6%AD%8C%E8%AF%8D%E7%BC%96%E6%9B%B2)
- 简单模式：[demo1.md](references/demo1.md)
- 风格里编曲：[风格编曲](references/%E9%A3%8E%E6%A0%BC%E7%BC%96%E6%9B%B2)

- 人声哼唱吟唱：如果你希望音乐中包含非语言的人声（如哼唱或吟唱），可以在歌词中提供发音音节，例如：
```
"ah, ah, ah, ah..."
"la, la, la, la..."
"mmm, mmm, mmm..."
"ooh, ooh, ooh..."
"hum, hum, hum..."`
```

## 注意事项

- 歌词中的 `---` 分隔线要删除
- markdown 格式标记（`**`、`#`、`` ` ``）要删除
- 括号 `(编曲说明)` 要转换为方括号 `[编曲说明]` 格式
- 韵律说明表格等元数据不放入歌词，只放可唱内容
- 风格描述要翻译成 MiniMax 能理解的关键词
