---
name: muse-lyrics-gen
description: Generate lyrics for Muse AI music projects following Lo-Fi sofa song conventions. Use when user asks to "生成歌词", "写歌词", "根据 design 写歌词", or when working with muse_ai project directories containing lyrics.design.md files. Reads design specifications and outputs lyrics.md with proper 8-beat structures, weak rhymes, and lazy murmuring tone.
agent_created: true
executable: false
---

# Muse Lyrics Gen

## Overview

Generate lyrics for Lo-Fi sofa songs following strict musical prosody rules. Input is a `lyrics.design.md` file containing song metadata, style requirements, and creative direction. Output is a `lyrics.md` file ready for AI music generation.

## Workflow

### Step 1: Locate Design File

Find the `lyrics.design.md` file in the project directory:
```
<project>/lyrics/lyrics.design.md
```

Read the design file to extract:
- Song title (first line, remove "歌名：" prefix)
- Creative inspiration/keywords
- Global settings (tempo, instruments, prohibited elements)

### Step 2: Load Prosody Rules

Load `references/lyric_prosody.md` into context for rhythm and rhyme guidelines.

### Step 3: Generate Lyrics

Follow the prosody rules strictly:

**8-Beat Structure:**
- 2 lines per group = 8 beats
- Line 1 (C chord, 4 beats): 3-4 syllables, gentle opening
- Line 2 (Em/B chord, 4 beats): 4-5 syllables, rhyme on last word

**Rhyme Design:**
- Use closed vowels: i / ü / ei韵部
- Only rhyme on line 2 of each group
- Near-rhymes acceptable, no strict 平仄

**Breathing Room:**
- Never fill all beats; leave half-beat air pockets
- Sentences shorter than 10 characters
- Use fragments and pauses

**Emotional Restraint:**
- Never expose emotions directly
- Use concrete details to imply feelings
- Avoid emotion words

### Step 4: Structure the Output

Organize lyrics with proper sections:
```
[Intro] → [Verse 1] → [Verse 2] → [Interlude] → [Chorus] → [Verse 3] → [Chorus] → [Outro]
```

Each section needs:
- Production notes in parentheses
- Lyrics lines with proper breathing
- Transition instructions

### Step 5: Write to File

Output to `<project>/lyrics/lyrics.md`

## Prosody Quick Reference

| Rule | Requirement |
|------|-------------|
| Line length | 3-6 characters |
| Beats per line | C chord: 3-4 syl, Em chord: 4-5 syl |
| Rhyme position | Only on line 2 of each group |
| Rhyme type | i/ü/ei韵部 (closed vowels) |
| Breath | Half-beat pause at line end |
| Emotion | Indirect, detail-based |

## 工程聚合

本技能的产物可被 `song_engineer` 技能聚合进统一的「歌曲工程MD」。产物到工程MD区块的字段对照：

| 本技能产物字段 | 工程MD区块 | 说明 |
|---------------|-----------|------|
| lyrics.design.md 歌名 | 元信息 > 歌名 | - |
| lyrics.design.md 曲风/BPM | 元信息 > 风格/BPM | 字段优先级低于 ai_chords_master |
| lyrics.design.md 全局设定（人声/配器/禁用） | 歌词 > 【全局设定】 | 直接映射 |
| lyrics.md 结构标签（[Verse]/[Chorus]等） | 歌词 | 直接内嵌或整体引用 |
| lyrics.md 韵律设计说明表 | 歌词 > 韵律设计说明 | 直接映射 |

**聚合触发**：当用户说「初始化工程」「聚合半成品」「诊断工程」时，由 song_engineer 读取本技能产物并按上表映射。本技能本身无需改动。

**诊断关联**：song_engineer 诊断时会检查歌词段落标签是否与工程MD段落结构表对齐（如 [Verse 1] 对应主歌A），以及韵部是否符合风格规范（沙发小曲用闭口音 i/ü/ei）。

工程MD格式规范见：`md/currdesign/工程MD格式规范.md`

## Resources

### references/lyric_prosody.md
Detailed prosody rules including chord progression mapping, syllable templates, and sofa song aesthetic guidelines. **Must be loaded before generating lyrics.**
