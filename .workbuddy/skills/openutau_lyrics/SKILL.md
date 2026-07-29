---
name: openutau_lyrics
description: >
  将中文歌词转换为 OpenUTAU 可唱的音素序列（CV Phonemes）。支持音节拆分、声母+韵母映射、音素优化。
  Triggers on: 歌词音素、音素设计、openutau lyrics、拼音转音素、中文歌词转音素、ustx 歌词编辑、生成 openutau 歌词
agent_created: true
---

# OpenUTAU Lyrics — 歌词音素设计技能 v2.0

## 概述

将中文歌词转换为 OpenUTAU 可唱的音素序列（CV Phonemes 格式）。基于 02_主唱.md 的逐音符级旋律数据，生成逐音节音素标签。

## 核心能力

1. **歌词 → CV Phonemes**：中文按音节拆分，映射到 OpenUTAU 音素库（声母+韵母）
2. **逐音符对齐**：根据旋律文件中每个字的音高+时值，对齐到对应音符
3. **音素优化**：调整音素边界，提升连读自然度
4. **多种格式输出**：CV / VC / VCV / 纯汉字（音素器自动转换）

## 触发词

歌词音素、音素设计、openutau lyrics、拼音转音素、中文歌词转音素、ustx 歌词编辑、生成 openutau 歌词、openutau_lyrics

## 输入输出

| 类型 | 路径 |
|------|------|
| 输入 | `workspace/project/{歌名}/song_engineer/track/02_主唱.md` |
| 输出 | `workspace/project/{歌名}/song_engineer/track/02_主唱_phonemes.md` |

## OpenUTAU 音素类型

### CV Phonemes（默认，推荐）
- 每个音符一个音节：`门=m+en`
- 格式：`声母+韵母`，韵母前加 `+` 分隔
- 零声母字直接用韵母：`啊=a`，`嗯=N`

### VC Phonemes
- 包含音节边界 + 尾音：`门=en+m`，`着=er+zh`
- 适合某些需要前后音连接的声库

### VCV Phonemes（日语风格）
- 前字尾音 + 后字声母 + 元音：`门=men+m+en`
- 适合某些日语/英语音素库

### 纯汉字（音素器自动转换）
- 直接输入汉字，OpenUTAU 音素器自动转换
- 需选择中文普通话音素器

## 中文音素映射规则

### 声母映射

| 声母 | 音素 | 示例 |
|------|------|------|
| b/p/m/f | b/p/m/f | 杯bei=be+b |
| d/t/n/l | d/t/n/l | 底di=di+d |
| g/k/h | g/k/h | 哥ge=ge+g |
| j/q/x | j/q/x | 脚jiao=j+iao |
| zh/ch/sh/r | zh/ch/sh/r | 着zhe=zh+er |
| z/c/s | z/c/s | 在zai=z+ai |
| y/w | y/w | 呀ya=a+y |
| ng | N | 嗯en=en+N |

### 韵母映射

| 韵母类型 | 音素 | 示例 |
|---------|------|------|
| 单元音 | a/o/e/i/u/v | 啊a=a，哦o=o，鹅e=e，衣i=i，乌u=u，迂v=v |
| 复元音 | ai/ei/ao/ou/ia/ie/ua/uo/ve | 爱ai=ai，诶ei=ei，奥ao=ao |
| 鼻音 | an/en/aN/eN/iN | 安an=an，恩en=en，昂ang=aN |
| 特殊 | er/ong/oN | 儿er=er，ong=oN |

### 特殊字处理

| 字 | 拼音 | CV音素 | 说明 |
|----|------|--------|------|
| 了 | le | l+e | 轻声 |
| 啊 | a | a | 零声母 |
| 嗯 | en | eN | 鼻音结尾 |
| 着 | zhe | zh+er | er韵 |
| 的 | de | d+e | 轻声 |

## 完整歌词音素对照表（CV 格式）

### 主歌A [Verse 1]

| 字 | 拼音 | CV音素 | 音高 | 时值 |
|----|------|--------|------|------|
| 门 | men | m+en | G#3 | 4分 |
| 虚 | xu | x+v | A#3 | 8分 |
| 掩 | yan | j+an | G#3 | 8分 |
| 着 | zhe | zh+er | F3 | 4分延 |
| 风 | feng | f+eN | G#3 | 4分 |
| 掀 | xian | x+ian | A#3 | 8分 |
| 了 | le | l+e | B3 | 4分延 |
| 快 | kuai | k+uai | A#3 | 8分 |
| 递 | di | d+i | G#3 | 4分延 |
| 鞋 | xie | x+ie | F3 | 4分 |
| 尖 | jian | j+ian | G3 | 8分 |
| 沾 | zhan | zh+an | F3 | 8分 |
| 雨 | yu | v | D#3 | 4分延 |
| 空 | kong | k+oN | F3 | 4分 |
| 调 | diao | d+iao | G3 | 8分 |
| 数 | shu | sh+u | A#3 | 4分 |
| 到 | dao | d+ao | G3 | 8分 |
| 七 | qi | q+i | F3 | 4分延 |
| 没 | mei | m+ei | A#3 | 4分 |
| 起 | qi | q+i | G#3 | 8分 |
| 身 | shen | sh+en | A#3 | 8分 |
| 窝 | wo | w+o | G#3 | 4分延 |
| 在 | zai | z+ai | G#3 | 8分 |
| 花 | hua | h+ua | F3 | 8分 |
| 海 | hai | h+ai | G#3 | 4分 |
| 里 | li | l+i | F3 | 全延 |
| 沙 | sha | sh+a | G#3 | 4分 |
| 发 | fa | f+a | F3 | 8分 |
| 陷 | xian | x+ian | D#3 | 8分 |
| 着 | zhe | zh+er | D3 | 4分延 |
| 杯 | bei | b+ei | D#3 | 4分 |
| 底 | di | d+i | F3 | 8分 |
| 淡 | dan | d+an | G3 | 8分 |
| 了 | le | l+e | F3 | 4分 |
| 去 | qu | q+v | D#3 | 4分延 |

### 主歌B [Verse 2]

| 字 | 拼音 | CV音素 | 音高 | 时值 |
|----|------|--------|------|------|
| 拖 | tuo | t+uo | F3 | 4分 |
| 鞋 | xie | x+ie | G3 | 8分 |
| 半 | ban | b+an | F3 | 8分 |
| 掉 | diao | d+iao | D#3 | 4分延 |
| 踩 | cai | c+ai | D#3 | 4分 |
| 过 | guo | g+uo | F3 | 8分 |
| 泥 | ni | n+i | G3 | 8分 |
| 和 | he | h+e | F3 | 4分 |
| 水 | shui | sh+v | D#3 | 4分延 |
| 冷 | leng | l+eN | D#3 | 4分 |
| 柜 | gui | g+v | F3 | 8分 |
| 发 | fa | f+a | D#3 | 8分 |
| 蓝 | lan | l+an | C3 | 4分延 |
| 没 | mei | m+ei | C3 | 4分 |
| 买 | mai | m+ai | D#3 | 8分 |
| 就 | jiu | j+iu | F3 | 8分 |
| 回 | hui | h+v | D#3 | 4分 |
| 去 | qu | q+v | C3 | 4分延 |
| 沙 | sha | sh+a | C3 | 4分 |
| 发 | fa | f+a | D#3 | 8分 |
| 空 | kong | k+oN | C3 | 8分 |
| 着 | zhe | zh+er | B2 | 4分延 |
| 没 | mei | m+ei | B2 | 4分 |
| 人 | ren | r+en | C3 | 8分 |
| 留 | liu | l+iu | D#3 | 8分 |
| 意 | yi | i | C3 | 4分 |
| 身 | shen | sh+en | D#3 | 4分 |
| 体 | ti | t+i | F3 | 8分 |
| 没 | mei | m+ei | G3 | 8分 |
| 动 | dong | d+oN | A#3 | 4分延 |
| 灵 | ling | l+iN | A#3 | 4分 |
| 魂 | hun | h+un | C4 | 4分 |
| 走 | zou | z+ou | A#3 | 8分 |
| 过 | guo | g+uo | G#3 | 8分 |
| 去 | qu | q+v | G3 | 4分延 |

### 间奏 [Interlude]

| 字 | 拼音 | CV音素 | 音高 | 时值 |
|----|------|--------|------|------|
| 嗯 | en | eN | G#3 | 全延 |
| 它 | ta | t+a | G#3 | 4分 |
| 没 | mei | m+ei | F3 | 8分 |
| 动 | dong | d+oN | G3 | 8分 |
| 又 | you | i+ou | F3 | 4分 |
| 像 | xiang | x+iaN | G3 | 8分 |
| 都 | dou | d+ou | A#3 | 8分 |
| 走 | zou | z+ou | G#3 | 4分 |
| 了 | le | l+e | F3 | 全延 |

### 副歌 [Chorus]

| 字 | 拼音 | CV音素 | 音高 | 时值 |
|----|------|--------|------|------|
| 杯 | bei | b+ei | C4 | 4分 |
| 底 | di | d+i | D4 | 8分 |
| 圈 | quan | q+uan | C4 | 8分 |
| 淡 | dan | d+an | A#3 | 4分延 |
| 投 | tou | t+ou | C4 | 4分 |
| 屏 | ping | p+iN | A#3 | 8分 |
| 卡 | ka | k+a | G#3 | 8分 |
| 半 | ban | b+an | F3 | 4分 |
| 截 | jie | j+ie | D#3 | 4分延 |
| 消 | xiao | x+iao | C4 | 4分 |
| 息 | xi | x+i | D4 | 8分 |
| 弹 | tan | t+an | C4 | 8分 |
| 出 | chu | ch+u | A#3 | 4分延 |
| 名 | ming | m+iN | C4 | 4分 |
| 字 | zi | z+i | A#3 | 8分 |
| 很 | hen | h+en | G#3 | 8分 |
| 熟 | shu | sh+u | F3 | 4分 |
| 悉 | xi | x+i | D#3 | 4分延 |
| 有 | you | i+ou | D4 | 4分 |
| 人 | ren | r+en | C4 | 8分 |
| 碰 | peng | p+eN | D4 | 8分 |
| 肩 | jian | j+ian | C4 | 4分延 |
| 风 | feng | f+eN | A#3 | 4分 |
| 晃 | huang | h+uaN | C4 | 8分 |
| 了 | le | l+e | A#3 | 8分 |
| 窗 | chuang | ch+uaN | G#3 | 4分 |
| 帘 | lian | l+ian | F3 | 4分延 |
| 细 | xi | x+i | C4 | 4分 |
| 线 | xian | x+ian | A#3 | 8分 |
| 反 | fan | f+an | G#3 | 8分 |
| 复 | fu | f+u | F3 | 4分延 |
| 却 | que | q+ve | F3 | 4分 |
| 没 | mei | m+ei | D#3 | 8分 |
| 人 | ren | r+en | D3 | 8分 |
| 在 | zai | z+ai | D#3 | 4分 |
| 意 | yi | i | D3 | 4分延 |

### 主歌A' [Verse 3]

| 字 | 拼音 | CV音素 | 音高 | 时值 |
|----|------|--------|------|------|
| 地 | de | d+e | G#3 | 4分 |
| 铁 | tie | t+ie | A#3 | 8分 |
| 报 | bao | b+ao | G#3 | 8分 |
| 站 | zhan | zh+an | F3 | 4分延 |
| 靠 | kao | k+ao | G#3 | 4分 |
| 门 | men | m+en | F3 | 8分 |
| 打 | da | d+a | D#3 | 8分 |
| 哈 | ha | h+a | D3 | 4分 |
| 欠 | qian | q+ian | D#3 | 4分延 |
| 手 | shou | sh+ou | D#3 | 4分 |
| 里 | li | l+i | F3 | 8分 |
| 攥 | zuan | z+uan | D#3 | 8分 |
| 皱 | zhou | zh+ou | C3 | 4分延 |
| 小 | xiao | x+iao | C3 | 4分 |
| 票 | piao | p+iao | D#3 | 8分 |
| 没 | mei | m+ei | F3 | 8分 |
| 目 | mu | m+u | G3 | 4分 |
| 的 | de | d+e | A#3 | 4分延 |
| 忘 | wang | w+aN | A#3 | 4分 |
| 了 | le | l+e | C4 | 8分 |
| 填 | tian | t+ian | A#3 | 8分 |
| 停 | ting | t+iN | G#3 | 4分延 |
| 在 | zai | z+ai | G#3 | 4分 |
| 第 | di | d+i | F3 | 8分 |
| 三 | san | s+an | D#3 | 8分 |
| 弦 | xian | x+ian | D3 | 4分延 |
| 它 | ta | t+a | D#3 | 4分 |
| 还 | hai | h+ai | F3 | 8分 |
| 在 | zai | z+ai | G3 | 8分 |
| 响 | xiang | x+iaN | A#3 | 4分延 |
| 人 | ren | r+en | G#3 | 4分 |
| 已 | yi | i | F3 | 8分 |
| 去 | qu | q+v | D#3 | 8分 |
| 了 | le | l+e | D3 | 4分 |
| 别 | bie | b+ie | C3 | 4分延 |

### 副歌重复 [Chorus 2]

| 字 | 拼音 | CV音素 | 音高 | 时值 |
|----|------|--------|------|------|
| 光 | guang | g+uaN | C4 | 4分 |
| 线 | xian | x+ian | D4 | 8分 |
| 晃 | huang | h+uaN | C4 | 8分 |
| 了 | le | l+e | A#3 | 4分延 |
| 吹 | chui | ch+v | C4 | 4分 |
| 了 | le | l+e | A#3 | 8分 |
| 我 | wo | w+o | G#3 | 8分 |
| 到 | dao | d+ao | F3 | 4分 |
| 那 | na | n+a | D#3 | 4分延 |
| 里 | li | l+i | C4 | 4分 |
| 都 | dou | d+ou | A#3 | 8分 |
| 散 | san | s+an | G#3 | 8分 |
| 了 | le | l+e | F3 | 4分延 |
| 飘 | piao | p+iao | F3 | 4分 |
| 到 | dao | d+ao | D#3 | 8分 |
| 那 | na | n+a | D3 | 8分 |
| 里 | li | l+i | C3 | 4分延 |

### 尾奏 [Outro]

| 字 | 拼音 | CV音素 | 音高 | 时值 |
|----|------|--------|------|------|
| 脚 | jiao | j+iao | C3 | 4分 |
| 麻 | ma | m+a | B2 | 4分 |
| 了 | le | l+e | C3 | 4分延 |
| 水 | shui | sh+v | B2 | 4分 |
| 凉 | liang | l+iaN | C3 | 4分 |
| 了 | le | l+e | B2 | 4分延 |
| 去 | qu | q+v | A#2 | 4分 |
| 吗 | ma | m+a | A#2 | 4分 |
| 去 | qu | q+v | G#2 | 4分 |
| 吗 | ma | m+a | G#2 | 4分延 |
| 算 | suan | s+uan | G2 | 4分 |
| 了 | le | l+e | G2 | 4分 |
| 算 | suan | s+uan | F#2 | 4分 |
| 啦 | la | l+a | F2 | 全延 |
| 那 | na | n+a | F2 | 4分 |
| 弦 | xian | x+ian | E2 | 8分 |
| 还 | hai | h+ai | D#2 | 8分 |
| 响 | xiang | x+iaN | D#2 | 4分延 |
| 嗯 | en | eN | C#2 | 全延 |
| 啊 | a | a | B1 | 全延 |

## OpenUTAU 使用步骤

1. 打开 OpenUTAU，加载工程或新建工程
2. 在 Singer 设置中选择中文普通话声库（如 `mei` / `澜` / `星尘` 等）
3. 在 Piano Roll 中选中 `02_主唱_v2.mid` 导出的音符
4. 逐个音符输入歌词（从 `02_主唱_phonemes.md` 复制 CV 音素）
5. 或直接粘贴汉字，让音素器自动转换

## 相关文件

```
.workbuddy/skills/openutau_lyrics/
├── SKILL.md                          # 本文件
└── scripts/
    ├── lyrics_to_phonemes.py         # 歌词转音素脚本
    └── pinyin_phoneme_map.json       # 拼音-音素映射表 v2.0
```

## 相关技能

- `muse-lyrics-gen` - 歌词设计
- `minimax-music-web` - MiniMax Music 3 网页端生成
- `song_engineer` - 歌曲工程编排
