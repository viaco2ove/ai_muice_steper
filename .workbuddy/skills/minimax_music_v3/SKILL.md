---
name: minimax_music_v3
description: 将歌词转换为 MiniMax Music 3 网页端可识别的格式。读取 muse_ai 项目的 lyrics.md 和 lyrics.design.md，输出带结构标签和编曲说明的纯文本歌词 + 风格描述，用于粘贴到 https://www.minimaxi.com/audio/music 网页端生成音乐。触发词：MiniMax 音乐生成、music v3、转换歌词格式、生成 MiniMax 歌词。
agent_created: true
---

# MiniMax Music v3 歌词格式化
[.env](../../../.env)
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
2. **编曲说明**：用 **
方式1（不稳定）：
方括号 `[...]`** 包裹，放在结构标签后的下一行，独占一行。这是 MiniMax 识别编曲提示的格式
方式2：
在prompt 里填写，但是有篇幅限制，2000 字
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
歌词
```
## [Intro]


## [Verse 1]
门虚掩着
风掀了快递
鞋尖沾雨
空调数到七
没起身
窝在花海里
沙发陷着
杯底淡了去


## [Verse 2]
拖鞋半掉
踩过泥和水
冷柜发蓝
没买就回去
沙发空着
没人留意
身体没动
灵魂走过去


## [Interlude]
…嗯…
…它没动…
…又像…
…都走了…


## [Chorus]
杯底圈淡
投屏卡半截
消息弹出
名字很熟悉
有人碰肩
风晃了窗帘
细线反复
却没人在意


## [Verse 3]
地铁报站
靠门打哈欠
手里攥皱
小票没目的
忘了填
停在第三弦
它还在响
人已去了别地


## [Chorus]
杯底圈淡
投屏卡半截
消息弹出
那名字很熟悉
有人碰肩
风晃了窗帘
光线晃了
吹了我到那里


## [Outro]
…脚麻了…
…水很凉…
…去吗去吗…
…算了算啦…
…那弦还响着…
…嗯…
…啊…
```
提示词
```
Lo-Fi 沙发小曲 / 慵懒民谣（沙发核 · 基础形态）。BPM 68，4/4 拍，Eb 大调（Capo 3），普通话。目标时长约 3 分钟（52 小节）。全程低输出，副歌不爆发，靠和弦色彩制造细微起伏。

## 人声要求

男声低吟（Lo-Fi Male Vocal），气声占比 40%+，真声为主，不用混声/嘶吼。轻声细语，自言自语感，对着空气哼唱；尾音轻轻带过不填满每拍。主歌音域 G#3~A#3 贴 Melodyne 扒谱动机，句末 vibrato；副歌上四度到 D4~A4（最高 A4），大跳处 portamento，四度跳进制造起伏。适度 vibrato（句尾）+ portamento（大跳处）+ 微转音。

## 核心配器

- 主吉他：钢弦木吉他 Acoustic Steel String，温暖分解，琴箱共鸣，Lo-Fi 质感，全曲
- 独奏吉他主：钢弦吉他五声音阶连奏 legato，击弦 hammer-on + 勾弦 pull-off + 滑弦 slide，旋律化不炫技，间奏 + 副歌点缀
- 辅助吉他 1：尼龙木吉他 Nylon Guitar，琶音旋律化，柔和铺垫
- 辅助吉他 2：爵士吉他 Jazz Guitar，Eb 布鲁斯音阶，推弦 bend + 滑弦 slide，克制不爆发
- 节奏吉他：钢弦木吉他，1 拍拍弦 slap + 2-4 拍勾弦柱体和弦，Lo-Fi 慵懒
- 和声：男声合唱，三度/六度平行，永远弱于主唱（主唱 1.0 / 和声 0.4），副歌加强主歌轻和
- 氛围垫音：合成器 Warm Pad，极淡铺底，跟和弦根音 Eb↔D 沙发下行，每 4 小节换音，ppp
- 自然白噪音：细雨声（前奏淡入）+ 风声（间奏）+ 远处模糊日常声（尾奏），淡入淡出
- 泛音点缀：吉他 12 品自然泛音 Eb4/Bb4，空灵点缀
- 轻贝斯：电贝斯，跟和弦根音 Eb↔D，每小节第 1 拍长音，低音量填补低频

## 段落结构（8 段 / 52 小节 / 约 3:05）

[Intro] 4 小节 0:00-0:14 纯吉他 + 雨声淡入
[Verse 1] 8 小节 0:14-0:42 主歌 A，Cadd9→C7sus4→Em9/B→Em11/B 循环
[Verse 2] 8 小节 0:42-1:11 主歌 B，Em9/B 转位为主，音区下移
[Interlude] 4 小节 1:11-1:25 吉他独奏加花 + 风声 + 气声虚词
[Chorus] 8 小节 1:25-1:53 副歌首现，音区上四度 D4~A4
[Verse 3] 8 小节 1:53-2:21 主歌 A'，回归 C7sus4，回环感
[Chorus] 8 小节 2:21-2:49 副歌重复，末句"吹了我到那里"替代
[Outro] 4 小节 2:49-3:04 Em7 单音泛音 + 远处日常声 + 气声渐无

## 段落编曲注记

- [Intro]：木吉他单音泛音余韵，极淡氛围垫音，细雨声淡入，无歌词，极简入曲
- [Verse 1]：Cadd9→C7sus4 分解节奏型，轻柔留白，人声低输出呢喃，G#3~A#3 贴主歌动机，平静慵懒
- [Verse 2]：Em9/B 转位为主，音区下移，氛围微暗，人声继续呢喃，迷茫内省
- [Interlude]：纯分解和弦，四小节留白，风声渐入，气声虚词
- [Chorus]：扫弦轻柔铺开，Em11/B 加 Cmaj9 色彩转换，人声略微舒展但绝不爆发，音区上四度 D4~A4（最高 A4）
- [Verse 3]：回归 C7sus4，回环感，人声呢喃，音区回落 G#3~A#3
- [Chorus 重复]：人声渐弱，最后一句换词"吹了我到那里"
- [Outro]：单音泛音缓慢淡出，远处模糊日常声淡入，气声渐无，安静收尾

## 和弦骨架

沙发下行进行：Cadd9 | C7sus4 | Em9/B | Em11/B | ×循环，副歌色彩转换 Em11/B | Cmaj9。每小节第 1 拍根音 C→B 半音滑动（实际 Eb→D）。结尾 Em7 单音泛音收束，像慢慢睡着。

## 节奏与动态

整体力度 pp~mp，全程禁止 f 以上。分解和弦为主，副歌可极轻空心扫弦。每句结尾留空像呼吸。副歌只比主歌多一点点气息支撑，不上 key 不加力度。

## 禁用红线

❌ 鼓组/卡洪/沙锤/任何打击乐 ❌ 重贝斯/失真吉他/电音/808 ❌ 副歌爆发/上 key/高音嘶吼 ❌ 强力和弦/大横按/增/减和弦 ❌ 女声/童声/多人和声组合。

## 文化底色

身体与灵魂的分裂漫游，随时随地进入别处，不抵达。场景锚点：沙发、雨、空调、快递、地铁、窗帘。慵懒、迷茫、内省、平静。禁现积极/励志/失恋。
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
