---
name: minimax-music-web
description: >
  Use when user wants to generate music via MiniMax Music 3 web interface
  (https://www.minimaxi.com/audio/music). Triggers on requests involving:
  - Pasting lyrics/style into the MiniMax web page
  - Manual music generation workflow
  - Preparing content for MiniMax Music 3 website
  - Muse AI song creation workflow (lyrics.design.md -> lyrics.md -> music)
  Do NOT use for API/CLI music generation (use minimax-music-api instead).
license: MIT
metadata:
  version: "1.0"
  category: creative
---

# MiniMax Music Web Skill

Prepare content for MiniMax Music 3 web interface (https://www.minimaxi.com/audio/music).
This skill converts lyrics design specifications into the format required by the web UI.

## Web UI Requirements

| Field | Max Length | Format |
|-------|------------|--------|
| 歌词 (Lyrics) | 3500 chars | 结构标签 + 编曲说明 + 歌词行 |
| 风格描述 (Style) | 2000 chars | 中文为主，逗号分隔 |

## Lyrics Format for MiniMax Music 3 Web

### Structure Tags (use Chinese labels)

```
[Intro]      - 前奏
[Verse]      - 主歌
[Chorus]     - 副歌
[Pre-Chorus] - 预副歌
[Bridge]     - 桥段
[Interlude]  - 间奏
[Outro]      - 尾奏
```

### Format Rules

1. **结构标签**：`[标签名]` 单独一行
2. **编曲说明**：紧跟标签后，**用方括号包裹** `[吉他轻柔分解...]`
3. **歌词行**：编曲说明后每行一句
4. **段落分隔**：段落间空一行
5. **气声/呢喃**：用 `…` 前缀（如 `…嗯…`）
6. **避免**：markdown 格式、英文括号、过多标点

### Example

```
[Intro]
[吉他分解和弦轻柔开场，木吉他单音泛音余韵，极淡氛围垫音，无歌词]


[Verse 1]
[吉他Cadd9到C7sus4分解节奏型，轻柔留白，人声低输出呢喃，无鼓组]
门虚掩着
风掀了快递
鞋尖沾雨
空调数到七


[Chorus]
[吉他扫弦轻柔铺开，Em11/B加Cmaj9色彩转换，人声略微舒展但绝不爆发，无鼓组]
杯底圈淡
投屏卡半截
消息弹出
名字很熟悉
```

## Style Format

### Structure

```
曲风标签, 情绪标签, 人声描述, 配器描述, 禁用项
```

### Common Tags (Chinese)

| Category | Tags |
|----------|------|
| 曲风 | Lo-Fi沙发, 慵懒民谣, 轻柔流行, 氛围, 独立民谣 |
| 情绪 | 平静, 慵懒, 随性, 迷茫, 疏离, 内省 |
| 人声 | 男声呢喃, 女声轻柔, 气声, 低声细语, 无明显情绪起伏 |
| 配器 | 木吉他分解, 钢琴, 氛围垫音, 极简编曲 |
| 禁用 | 无鼓组, 无电音, 无副歌爆发, 无重贝斯 |

### Example

```
Lo-Fi沙发小曲, 慵懒随性, 男声低输出呢喃, 木吉他分解和弦为主极淡氛围垫音,
无鼓组, 无电音, 无副歌爆发, 极简留白
```

## Workflow

### Step 1: Check for Design File

Look for `lyrics.design.md` in the project directory:
```
workspace/<song_name>/lyrics/lyrics.design.md
```

If exists, read and extract:
- Global settings (BPM, key, instruments)
- Song structure (Verse/Chorus/Bridge layout)
- Mood/tone requirements
- Chord progression
- Style tags

### Step 2: Generate Lyrics (if needed)

Use `muse-lyrics-gen` skill to generate lyrics from design:
- Follow 8-beat/group structure
- Use closed vowels (i/ü/ei) for rhyming
- Keep sentences short (3-6 characters)
- Leave space for breath marks

### Step 3: Convert to MiniMax Format

Convert lyrics to MiniMax Music 3 format:
1. Use Chinese structure tags `[Verse]` not `[verse]`
2. Add arrangement notes in `[...]` after each tag
3. Keep lyrics under 3500 characters
4. Convert style to Chinese comma-separated format

### Step 4: Output Files

Save to project directory:
```
workspace/<song_name>/
├── lyrics_minimax.txt      # Lyrics for web paste
├── style_minimax.txt       # Style for web paste
└── README_minimax.md       # Instructions
```

### Step 5: Guide User

Tell user to:
1. Open https://www.minimaxi.com/audio/music
2. Select "Music 3" model
3. Paste lyrics into lyrics field
4. Paste style into style field
5. Turn off "Pure Music" toggle
6. Set quantity to 2
7. Generate

## 控制标签参考

完整的段落控制标签体系（编曲、人声、情绪、节奏、禁用）见：
[references/control_tags.md](references/control_tags.md)

## Related Skills

- `muse-lyrics-gen` - 从歌词设计规范生成歌词
- `minimax-music-api` - API/CLI 方式生成音乐
