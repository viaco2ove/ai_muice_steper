---
name: minimax-music-api
description: >
  Use when user wants to generate music via MiniMax Music API (programmatic/CLI).
  Triggers on requests involving API calls, command-line tools (mmx), programming
  integration, or batch music generation. Do NOT use for web-based generation
  or when user wants to manually paste content into a website.
license: MIT
metadata:
  version: "1.0"
  category: creative
executable: false
---

# MiniMax Music API Skill
[.env](../../../.env)
Generate songs using the **mmx CLI** tool with MiniMax API. This is for programmatic
/CLI usage. For web-based generation, use `minimax-music-web` skill instead.

## Prerequisites

**mmx CLI** (required):
```bash
# Check if installed
command -v mmx && mmx --version || echo "mmx not found"

# Install (requires Node.js)
npm install -g mmx-cli

# Authenticate (first time only)
mmx auth login --api-key <your-minimax-api-key>

# Verify
mmx quota show
```

## Models

| Model | Command | Description |
|-------|---------|-------------|
| music-2.6-free | `mmx music generate` | Main music generation |
| music-cover-free | `mmx music cover` | Cover / style transfer |

## Core Commands

### Generate with auto-lyrics
```bash
mmx music generate \
  --prompt "<English prompt>" \
  --lyrics-optimizer \
  --genre "<genre>" --mood "<mood>" --vocals "<style>" \
  --instruments "<instruments>" --bpm <bpm> \
  --out <output_path>.mp3 \
  --quiet --non-interactive
```

### Generate with user lyrics
```bash
mmx music generate \
  --prompt "<English prompt>" \
  --lyrics "<lyrics with [verse], [chorus] markers>" \
  --genre "<genre>" --mood "<mood>" --vocals "<style>" \
  --out <output_path>.mp3 \
  --quiet --non-interactive
```

### Generate instrumental
```bash
mmx music generate \
  --prompt "<English prompt>" \
  --instrumental \
  --genre "<genre>" --mood "<mood>" \
  --instruments "<instruments>" --bpm <bpm> \
  --out <output_path>.mp3 \
  --quiet --non-interactive
```

### Cover mode
```bash
mmx music cover \
  --prompt "<cover style>" \
  --audio-file <source.mp3> \
  --out <output_path>.mp3 \
  --quiet --non-interactive
```

## Structured Parameters

Prefer these over cramming everything into `--prompt`:

| Flag | Description | Example |
|------|-------------|---------|
| `--genre` | Music genre | `lo-fi, folk, ambient` |
| `--mood` | Emotional tone | `melancholy, peaceful` |
| `--vocals` | Vocal style | `soft female, whispered` |
| `--instruments` | Instruments | `acoustic guitar, piano` |
| `--bpm` | Tempo | `68, 90, 120` |
| `--key` | Musical key | `C, Am, Eb` |
| `--structure` | Song structure | `verse-chorus-verse` |

## Lyrics Format for API

Use English section markers:
```
[Intro]
[Verse 1]
[Chorus]
[Bridge]
[Outro]
```

## Storage

Default output: `~/Music/minimax-gen/`
Filename format: `YYYYMMDD_HHMMSS_<slug>.mp3`

## Error Handling

| Error | Action |
|-------|--------|
| mmx not found | `npm install -g mmx-cli` |
| Auth error (code 3) | `mmx auth login` |
| Quota exceeded (code 4) | Report limit, suggest waiting |
| API timeout (code 5) | Retry once |
| Content filter (code 10) | Adjust prompt |
| Invalid lyrics format | Auto-fix section markers |

## 控制标签参考

完整的 API 参数（--vocals、--mood、--genre、--instruments、--avoid 等）见：
[references/control_tags.md](references/control_tags.md)

## Prompt Writing Guide

See [references/prompt_guide.md](references/prompt_guide.md) for detailed vocabulary.

---

**Related skills:**
- `minimax-music-web` - 网页端手动粘贴生成
- `muse-lyrics-gen` - 歌词设计与生成

https://platform.minimaxi.com/docs/api-reference/music-generation