---
name: melody_master
description: 旋律设计与改编技能。当用户想要设计/改编主旋律、分析参考曲旋律、写人声旋律时触发。
agent_created: true
---

# Melody Master 旋律设计技能

## 能力概览

基于参考曲扒谱 + 旋律写作规范 + 转音设计，重写/优化人声主旋律。

## 核心输入

| 来源 | 内容 |
|------|------|
| 参考曲 pitch.csv | 扒谱提取的真实旋律音高（时间/MIDI/置信度） |
| 旋律写作规范 | `md/kb_repo/info/主旋律/如何写出好听的主旋律.md` |
| 转音设计 | `md/kb_repo/info/主旋律/转音设计.md` |
| 目标歌曲 | `workspace/project/{歌名}/song_engineer/track/02_主唱.md`（已有旋律草稿）|

## 旋律写作黄金规则（核心）

### 音域控制
- 舒适区间：**低音 C3 ~ 高音 F4**
- 副歌最高音不连续长音
- 以级进（1-2度）+ 小跳（3-4度）为主，禁止连续大跳

### 音高走向
- 温柔抒情：**下行为主**
- 轻快甜歌：**小波浪起伏**
- 副歌高潮：先上行推高，再缓慢下行回落
- 禁止直线往上/往下

### 节奏搭配
- 长短音结合，重拍放高音长音
- 句尾统一拉长音（BREC 气息曲线空间）
- 禁止均分八分音符（最机械）

### 发展手法
- **起-承-转-合** 四句体（8小节一段）
- 重复变化：动机重复、同头换尾、模进
- 副歌高潮：上行模进 + 音域对比

## 转音设计规范

- 主歌：少转音，平稳级进
- 副歌：1处标志性转音（记忆点）
- 大跳后必须反向级进回填
- 长音：线性级进滑音（BREC 配合）

## 输出

重写后的 `02_主唱.md` 逐音符旋律表（字/音名/时值/拍位/力度），符合：
- 目标调（Eb 大调）
- 目标 BPM
- 人声音域 G#3~A4
- 参考曲的旋律气质（级进为主、小波浪）
- 规避机械感的节奏设计

## 参考旋律获取

```bash
# 1. 用 audio_chord_recognizer 扒参考曲
python .workbuddy/skills/audio_chord_recognizer/scripts/full_analysis.py input.wav -o workspace/audio_output/{song}/

# 2. 读 pitch.csv 提取旋律
python -c "
import csv
with open('melody/pitch.csv') as f:
    for row in csv.DictReader(f):
        if float(row['midi']) > 0 and float(row['prob']) > 0.3:
            print(row['time'], row['midi'], row['note'])
"
```

## 工程聚合

重写后的 `02_主唱.md` 替换 song_engineer 里的原有旋律，供后续 ust_generator.py → .ustx → OpenUTAU 渲染使用。