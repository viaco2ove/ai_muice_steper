---
name: xstudio_lyrics
description: >
  为网易 X Studio（AI 歌手）生成逐音符歌词：一字对一音、转音符 "-"、MIDI 内嵌 lyric 元事件。
  解决 MIDI+歌词错位问题——X Studio 导入 MIDI 时勾选「同步导入歌词信息」即可绝对对齐。
  Triggers on: xstudio 歌词、x studio 歌词、网易 X Studio、人声歌词生成、svip3 歌词、虚拟歌手歌词
agent_created: true
entry_script: "scripts/gen_xstudio_lyrics.py"
params: {"--project": "歌曲名(required)", "--midi": "MIDI文件名(默认02_主唱.mid)"}
executable: true
---

# X Studio Lyrics — 网易 X Studio 歌词生成技能 v1.0

## 概述

为**网易 X Studio**（xstudio.music.163.com，AI 虚拟歌手）生成逐音符歌词。
与 OpenUTAU 不同，X Studio 的歌词规则更简单，但**最易错位**——本技能用 3 重保障对齐：
1. **一字对一音**：每个 MIDI 音符恰好一个歌词（汉字）
2. **转音符 "-"**：一字多音时，后续音符填 `-`（前字发音延长）
3. **MIDI 内嵌 lyric 元事件**：导入时勾选「同步导入歌词信息」→ 绝对不错位

## 触发词

xstudio 歌词、x studio 歌词、网易 X Studio、人声歌词生成、虚拟歌手歌词、svip3 歌词、xstudio_lyrics

## 输入输出

| 类型 | 路径 |
|------|------|
| 输入 MIDI | `workspace/project/{歌名}/song_engineer/track/02_主唱.mid` |
| 输入歌词 | 从歌词源自动解析（SKILL.md 歌词表 或 --lyrics 参数） |
| 输出 | `workspace/project/{歌名}/song_engineer/ai-track/xstudio/` |
| ├ 歌词txt | `{轨名}_xstudio_lyrics.txt`（逐音符歌词，直接粘贴 X Studio） |
| ├ 内嵌MIDI | `{轨名}_lyric.mid`（含 lyric 元事件，X Studio 导入自动同步） |
| └ 对照表 | `{轨名}_xstudio.md`（音符#/小节.拍/音高/时值/歌词/拼音） |

## X Studio 歌词规则（与 OpenUTAU 的区别！）

| 规则 | OpenUTAU | **X Studio** |
|------|----------|--------------|
| 每音符歌词 | 音素（m+en） | **汉字**（自动转拼音）或拼音 |
| 一字多音 | 音素拼接 | **转音符 `-`**（前字发音延长到当前音符） |
| 休止符 | R | **无专用休止符**——音符之间留空即是休止 |
| 输入方式 | Piano Roll 粘贴音素 | 双击音符连续输入，或右键【编辑全部歌词】粘贴 |
| 对齐保障 | 手工 | **MIDI lyric 元事件**（导入时同步） |

⚠️ **关键差异（本项目踩坑）**：
- X Studio **不识别 R 作为休止**——没歌词的音符会默认唱"啦"！
- 休止的正确做法：MIDI 中音符间**留空**（不画音符），不需要任何歌词标记
- 装饰音/短音：不该删也不该留空——用 `-` 转音连到前字，AI 歌手会唱出花腔

## 对齐算法（核心）

1. **按段落分块**：V1(5-12) V2(13-20) 间奏(21-24) 副歌(25-32) 主歌A'(33-40) 副歌2(41-47) 尾奏(48-52)
2. **保持时间顺序**：段内歌词按小节.拍位顺序逐一匹配音符
3. **长音优先配词**：歌词字优先落在时值长的音符上（阈值从 3 拍��级下调至 90 ticks）
4. **短音 = 装饰音**：未配词的短音一律填 `-`（转音延音），**绝不填 R**
5. **输出三重保障**：txt + 内嵌 lyric MIDI + 对照表

## 使用步骤

```bash
# 1. 生成歌词（自动解析歌词源）
./.venv/python.exe .workbuddy/skills/xstudio_lyrics/scripts/gen_xstudio_lyrics.py \
    --project 走在 --midi 02_主唱.mid --track 02_主唱

# 2. X Studio 操作
#    a. 拖入 {轨名}_lyric.mid（勾选「同步导入歌词信息」）→ 歌词自动对齐！
#    b. 或导入原 MIDI → 右键音符【编辑全部歌词】→ 粘贴 {轨名}_xstudio_lyrics.txt
#    c. 选择 AI 歌手 → 渲染 → 导出人声 WAV
```

## 歌词源优先级

1. `--lyrics "门,虚,掩,..."` 逗号分隔字符串
2. `--lyrics-file path`（每行一字，或 "字 拼音" 两列）
3. 自动解析 `openutau_lyrics/SKILL.md` 歌词对照表（若存在）

## 校验输出

脚本运行后检查：
- `歌词利用率: 187/187`（=100% 表示每字都有音符）
- `R 数: 0`（X Studio 不需要 R，出现 R 说明有 bug）
- 内嵌 MIDI 生成成功：`{轨名}_lyric.mid`

## 相关技能

- `openutau_lyrics` - OpenUTAU 音素歌词（CV 音素格式）
- `muse-lyrics-gen` - 歌词设计
- `song_engineer` - 歌曲工程编排
