https://platform.minimaxi.com/docs/token-plan/minimax-cli

Minimax CLI (`mmx`) 的音乐相关接口主要通过 `mmx music` 命令族提供，涵盖**文生音乐**、**歌词创作**、**纯音乐**和**翻唱生成**等能力。以下是具体接口汇总：

mmx music --help
---

### 1. 文生音乐（基础生成）
```bash
mmx music generate --prompt "轻快爵士风格的歌曲，主题是夏天的海边" --out jazz-summer.mp3
```
- 通过 `prompt` 描述音乐风格、情绪、主题
- 使用 `--out` 指定输出文件路径（默认保存到 `minimax-output/` 目录）

---

### 2. 带歌词的音乐生成
```bash
mmx music generate --prompt "Upbeat pop" --lyrics "[verse] La da dee, sunny day"
```
- `--lyrics` 传入自定义歌词
- 歌词需使用段落标记（如 `[verse]`、`[chorus]` 等），否则生成质量会下降

---

### 3. 纯音乐 / 器乐模式
支持生成无歌词的纯器乐作品（instrumental mode），在 prompt 中描述即可，不传入 `--lyrics` 参数。

---

### 4. 歌词自动优化（Auto Lyrics）
支持自动优化或生成歌词后再进行音乐创作。

---

### 5. 翻唱生成（Music Cover）
支持基于已有歌曲生成不同风格的翻唱版本，对应底层 API 的 `music-cover` 模型：

| 模式 | 说明 | 对应 API 流程 |
|------|------|--------------|
| **一步翻唱** | 直接传入参考音频 URL，系统自动 ASR 提取歌词并生成翻唱 | `POST /v1/music_generation`，传 `audio_url` + `prompt` |
| **两步翻唱** | 先调用预处理接口提取音频特征和歌词，修改后再生成 | ① `POST /v1/music_cover_preprocess` → ② `POST /v1/music_generation` 传 `cover_feature_id` + 修改后的 `lyrics` |

两步翻唱中，预处理接口返回：
- `cover_feature_id`：音频特征 ID（24 小时有效）
- `formatted_lyrics`：带 `[Verse]`、`[Chorus]` 标签的结构化歌词（可自由编辑）

---

### 6. 其他运维命令
```bash
mmx quota          # 查看剩余额度（音乐生成消耗较大）
mmx config show    # 查看当前配置（region、默认模型等）
```

---

### 底层模型对应关系
| CLI 命令 | 底层模型/能力 |
|----------|--------------|
| `mmx music generate` | Music 3.0（文生音乐） |
| 翻唱功能 | `music-cover` 模型 |

> **注意**：使用 `mmx music` 需要先通过 `mmx auth login --api-key sk-xxxxx` 完成认证，并确保已订阅 MiniMax Token Plan 以获得额度。
> 
> 
# Cover — generate a cover version from a reference audio file
mmx music cover --prompt "Jazz, piano, warm female vocal" --audio-file original.mp3 --out cover.mp3
mmx music cover --prompt "Indie folk" --audio https://example.com/song.mp3 --out cover.mp3
```cite🛠web_search:4#1:~:text=Cover — generate a cover version...--audio https://example.com/song.mp3

---

### 2. 官方中文文档

`README_CN.md` 中功能特性部分明确写道：

> **音乐生成** — 文生音乐，支持自定义歌词、纯音乐、自动生词，**以及基于参考音频的 Cover 生成**cite🛠web_search:4#13:~:text=音乐生成 — 文生音乐...以及基于参考音频的 Cover 生成

---

### 3. SDK 文档（代码层面）

`SDK.md` 中详细描述了两步翻唱的代码调用方式，包括 `cover_feature_id` 和 `audio_url` 参数：cite🛠web_search:4#12:~:text=One-step cover...Two-step cover...cover_feature_id

---

### 4. 代码提交记录

GitHub Actions 中有一条提交记录标题为：`feat: add music cover command and upgrade to music-2.6`cite🛠web_search:4#11:~:text=feat: add music cover command and upgrade to music-2.6

---
