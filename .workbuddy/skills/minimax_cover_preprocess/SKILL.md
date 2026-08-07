---
name: minimax_cover_preprocess
description: >
  MiniMax「两步翻唱」技能（music-cover）。先提纯纯人声干音并调用 music_cover_preprocess
  前处理接口拿到 cover_feature_id + ASR 歌词 + 结构时间戳，人工校正歌词对齐点后，
  再用 cover_feature_id + 修正歌词 + prompt 调 music_cover 生成。解决一步 cover 翻车
  （上传带伴奏整曲→模型把伴奏当主旋律、free 模型乱改声线）的问题。铁律：只传纯人声干音、
  用 music-cover（非 free）、歌词须人工校正后才生成。触发词：两步翻唱、minimax cover、
  翻唱前处理、cover_feature_id、提纯干音翻唱。
agent_created: true
entry_script: "scripts/cover_two_step.py"
params: {"--vocals": "纯人声干音路径", "--source": "整曲(自动demucs提纯)", "--out-dir": "Step1输出目录", "--prompt": "目标风格", "--out": "输出mp3"}
executable: true
---

# MiniMax 两步翻唱（music-cover）

## 为什么不用一步 cover

上一个版本直接 `mmx music cover --audio-file full_remix.wav`（带伴奏整混音）一步生成，
结果**翻车**：声线变成女声、编曲和旋律跟原曲毫无关系。

根因有两条：
1. **传了带伴奏的整曲** → MiniMax 的 cover 模型把背景吉他/贝斯当成「主旋律」去提取，
   人声反而被当成伴奏，于是重生成时旋律全跑偏。
2. **用了 `music-cover-free`** → 免费模型自由度高、可控性差，随意改声线（变女声）。

两步流程从根上修掉这两点：
- **只传纯人声干音**（先用 UVR5 / Ultimate Vocal Remover / demucs 提纯），模型只听到人声，
  提取的旋律/歌词才准。
- **用 `music-cover`（付费）** 而不是 free，声线/编曲更可控。
- **前处理先拿歌词+结构，人工校正后再生成**，避免 ASR 错字/段落错位被直接采用。

## 两步流程总览

```
[纯人声干音]  ← 已有干音直接给，或整曲经 demucs 提纯，wav 转mp3 ,降低体积不然无法上传。
      │
      ▼  Step1: POST /v1/music_cover_preprocess  (model=music-cover)
      ├─ cover_feature_id   (24h 有效，相同音频 MD5 去重)
      ├─ formatted_lyrics    (ASR 提取的歌词，带 [Verse]/[Chorus] 标签)
      └─ structure_result    (JSON：各段类型 intro/verse/chorus...+起止时间戳)
      │
      ▼  【人工校正】改 formatted_lyrics.txt 的错字/段落对齐（对照 structure_result）
      │
      ▼  Step2: POST /v1/music_generation  (model=music-cover,
      │         cover_feature_id + 修正后 lyrics + prompt, output_format=url)
      │   ★ 同步阻塞接口：POST 保持连接直到返回 data.audio_url，直接下载
      └─ 无 query_async_task 端点（音乐用返回 404），不要轮询
```

## 输入


指定发送的整曲 （默认 workspace/project/{song}/song_engineer/track/full_remix.wav）
人声干音wav 或者MP3 （默认 workspace/project/{song}/song_engineer/track/singer）
参考歌词 （默认 workspace/project/{song}/song_engineer/track/）
歌曲风格（默认从orkspace/project/{song}/project.md 获取，）

## 输出
`workspace/project/{song}/song_engineer/cover_minimax/` 下面：
- `cover_preprocess.json` — Step1 产物（cover_feature_id 等）
- `formatted_lyrics.txt` — ASR 提取歌词（需人工校正）
- `formatted_lyrics.corrected.txt` — 校正后歌词（Step2 实际发送）
- `structure_result.txt` — 各段时间戳
- `02_主唱_v7_upload.mp3` — 干音转码后的实际上传文件（压体积）
- `generate_meta.json` — Step2 提交后写入（model/cover_feature_id/out/提交时间，无 task_id，因同步接口）
- `progress.md` — Step2 实时进度记录（见下「进度检测」）
- `cover_minimax_v2.mp3` — 最终翻唱成品（mp3，非 wav）

## 铁律（务必遵守）

1. **只传纯人声干音**，绝不传带伴奏的整混音。
   - 本项目已有现成干音：`workspace/project/{song}/song_engineer/track/singer/02_主唱_v7.wav`
     （OpenUTAU 导出的真人声，本身就是提纯后的）。直接 `--vocals` 给它。
   wav 转 mp3 ,降低体积不然无法上传。
   - 若只有整曲，用 `--source` 让脚本自动 demucs 提纯（htdemucs 两stems=vocals）。
2. **用 `music-cover`（付费）**，脚本默认就是这个，不要改成 `music-cover-free`。
3. **cover_feature_id 24h 有效**，必须等人工校正歌词后再跑 Step2，不要一次性自动连跑。
4. `lyrics` 字段长度 [10,1000]，`prompt` 长度 [10,300]，超出会被拒。

## 用法
### 知识库
[md/kb_repo/info/ai_tools/minimax/minimax_mmx_muisc.md]
[md/kb_repo/info/ai_tools/minimax/minimax_api_muisc.md]

### Step1 前处理（提取歌词+结构，供校正）

```bash
# 直接给纯人声干音（推荐，本项目场景）
.venv/python.exe .workbuddy/skills/minimax_cover_preprocess/scripts/cover_two_step.py preprocess \
  --vocals "workspace/project/{song}/song_engineer/track/singer/02_主唱_v7.wav" \
  --out-dir "workspace/project/{song}/song_engineer/cover_minimax"

# 或给整曲，自动 demucs 提纯
... preprocess --source "整曲.wav" --out-dir <dir>
```

产出（在 `--out-dir`）：
- `cover_preprocess.json` — cover_feature_id / audio_duration / structure_result / vocals_file
- `formatted_lyrics.txt` — **ASR 提取的歌词，需人工校正**（改这个文件）
- `structure_result.txt` — 各段起止时间戳，对照用

### 人工校正

打开 `formatted_lyrics.txt`：
- 修正 ASR 错字（如「名字很熟悉」被听成近音字）
- 核对段落标签 `[Verse]`/`[Chorus]` 是否与 `structure_result.txt` 的时间戳对齐
- 保留 `[Intro]`/`[Verse]`/`[Chorus]`/`[Bridge]`/`[Outro]` 等结构标签

### Step2 生成（校正后）

```bash
.venv/python.exe .workbuddy/skills/minimax_cover_preprocess/scripts/cover_two_step.py generate \
  --preprocess-json "workspace/project/{song}/song_engineer/cover_minimax/cover_preprocess.json" \
  --lyrics "workspace/project/{song}/song_engineer/cover_minimax/formatted_lyrics.txt" \
  --prompt "Lo-fi sofa song, warm male vocal, soft acoustic guitar, relaxed and intimate" \
  --out "workspace/project/{song}/song_engineer/cover_minimax/cover_minimax_v2.mp3"
```

> 注意：`--lyrics` 传的是**校正后**的 `formatted_lyrics.txt`（改完保存即可）。

## API 契约速查（脚本已封装）

**Step1** `POST /v1/music_cover_preprocess`
- Header: `Authorization: Bearer <key>`, `Content-Type: application/json`
- Body: `{"model":"music-cover","audio_base64":"..."}`（或 `audio_url`）
- 响应: `cover_feature_id` / `formatted_lyrics` / `structure_result`(JSON串) / `audio_duration` / `trace_id`

**Step2** `POST /v1/music_generation`（同步阻塞，无异步轮询端点）
- Body: `{"model":"music-cover","cover_feature_id":"...","lyrics":"...","prompt":"...","output_format":"url"}`
  （`cover_feature_id` 与 `audio_*` 互斥；传 feature_id 时 lyrics 必填）
- 同步：POST 保持连接直到生成完成，响应里带音频。实测返回结构：音频 URL 在 **`data.audio`** 字段
  （`data.audio_url` 反而是空），脚本对「`audio_url`/URL/`audio`(hex/base64)」三种情况都做了兼容。
  **没有** `query_async_task` 之类的进度端点（对音乐返回 404），不要轮询。
- 进度靠 `progress.py` 的 Heartbeat：等待期间每 30s 写一条「生成中（已等待 N 分）」到 progress.md。

鉴权：`.env` 的 `minimax_api_key`；base_url 读 `mmx config`（region=cn，默认 `https://api.minimaxi.com`）。

## 与 minimax-music-api 的关系

- `minimax-music-api` 的 `mmx music cover` 是**一步生成**，不支持前处理/歌词校正，
  且本项目用它出了女声翻车问题 → 本技能是它的「可控升级替代」，专治一步 cover 的坑。
- `minimax-music-web` 是网页端手动粘贴，不适用接口流程。

## 进度检测

重要事实（已实测纠正）：MiniMax 的 `music_cover` / `music_generation` 是**同步阻塞接口**，
POST 会一直保持连接直到音频生成完，直接把 `data.audio_url` 返回在响应里。**不存在**
异步进度端点（`query_async_task` 对音乐返回 404）。所以没有百分比进度可拉取——
进度只能是「提交 → 等待心跳(已耗时) → 完成/失败」。

`progress.py` 提供 `Heartbeat` 上下文管理器：`generate` 把阻塞的 POST 包在
`with progress.Heartbeat(progress.md, interval=30):` 里，进入时记「提交」，
开后台线程每 30s 写一条「生成中（已等待 N 分）」，退出时停线程；拿到响应后再写「完成/失败」。

**Step2 自动记录**：每次 `generate` 运行都会写 `progress.md`（含表头）和 `generate_meta.json`，
不再黑屏。后台任务也能看到心跳行。

> 说明：本项目 2026-08-07 第一次 v2 生成（SWHIZQ）用了**错误的异步轮询端点**（`query_async_task` 对音乐 404），
> 导致轮询全程失败、最后「轮询超时」退出，`cover_minimax_v2.mp3` 未生成。改成同步接口后重跑（task 1Q098E）
> 又踩到第二个坑：响应把音频 URL 放在 `data.audio` 而非 `data.audio_url`，旧代码当 hex 解码直接 ValueError。
> 修复为「URL/hex/base64 三路兼容 + 原始响应落盘 generate_resp.json」后，task 3QG1GC 才真正成功产出
> `cover_minimax_v2.mp3`（5.81MB，3:01，44.1kHz 立体声）。

## 依赖

- Python：`requests`（API 调用）。根 `.venv` 已装。
- 干音提纯：`demucs`（根 `.venv` 已装 htdemucs）。仅在用 `--source` 整曲时才需要。
- 仅 Step1 需要网络上传；Step2 也需要网络（提交+等待返回+下载）。
