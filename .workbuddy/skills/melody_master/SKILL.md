---
name: melody_master
description: 旋律设计与改编技能。当用户想要设计/改编主旋律、分析参考曲旋律、写人声旋律时触发。
agent_created: true
executable: false
---

# Melody Master 旋律设计技能
[.env](../../../.env)
## 能力概览

基于参考曲扒谱 + 旋律写作规范 + 转音设计，重写/优化人声主旋律。

## 核心输入

| 来源 | 内容 |
|------|------|
| 参考曲 pitch.csv | 扒谱提取的真实旋律音高（时间/MIDI/置信度） |
| 旋律写作规范 | `md/kb_repo/info/主旋律/如何写出好听的主旋律.md` |
| 转音设计 | `md/kb_repo/info/主旋律/转音设计.md` |
| 目标歌曲 | `workspace/project/{歌名}/song_engineer/track/02_主唱.md`（已有旋律草稿）|

## 旋律写作黄金规则（只是个参考）

### 音域控制
根据歌曲特点
下面只是个例子：
- 舒适区间：**低音 C3 ~ 高音 F4**
- 副歌最高音不连续长音
- 以级进（1-2度）+ 小跳（3-4度）为主，禁止连续大跳

### 音高走向
根据歌曲特点
下面只是个例子：
- 温柔抒情：**下行为主**
- 轻快甜歌：**小波浪起伏**
- 副歌高潮：先上行推高，再缓慢下行回落
- 禁止直线往上/往下

### 节奏搭配
根据歌曲特点
下面只是个例子：
- 长短音结合，重拍放高音长音
- 句尾统一拉长音（BREC 气息曲线空间）
- 禁止均分八分音符（最机械）

### 发展手法
根据歌曲特点
下面只是个例子：
- **起-承-转-合** 四句体（8小节一段）
- 重复变化：动机重复、同头换尾、模进
- 副歌高潮：上行模进 + 音域对比

## 转音设计规范
根据歌曲特点
下面只是个例子：
- 主歌：少转音，平稳级进
- 副歌：1处标志性转音（记忆点）
- 大跳后必须反向级进回填
- 长音：线性级进滑音（BREC 配合）

## 输出格式

### MD 文件必须包含
例如：02_主唱
每次生成/修改 `02_主唱.md` 或 `02_主唱.json` 后，MD 文件必须包含以下结构：
- 轨道信息表（轨道ID、乐器、角色、段落参与、状态）
- 旋律设计规则（音域、走向、节奏、发展手法等本次设计的决策）
- 段落设计表（小节×歌词×音域×力度×特色）
- 和弦进行表（从 01_吉他/08_节奏吉他 的同名 MD 中复制）
- **SoundFont / 最终音色** 段：
  ```
  ## SoundFont / 最终音色
  - SF2: **Timbres Of Heaven GM_GS_XG_SFX V 3.4 Final**(program 54, Voice Oohs)
  - 成品: MuseSounds Sopranos (museUID=19), 气声呢喃质感
  ```
SF2 默认为口风琴。如不是新的生成，是修改不要擅自修改音色。  

- 歌词全文

### JSON 格式规范
notes 数组每元素必须包含：note, actual, midi, duration, beat_pos, dynamics, velocity, technique, chord, char。
beat_pos 三段 1-based：`小节.拍.子拍`（如 `5.2.1`）。

### WAV 渲染
```
# 步骤 1：生成 mscx
.venv/python.exe .workbuddy/skills/musescore-cooperate/scripts/mscx_generator.py \
    --project {歌名} --tracks "02_主唱"

# 步骤 2：MuseScore 渲染（用 MuseSounds 保证音质）
"C:\Program Files\MuseScore 4\bin\MuseScore4.exe" -f \
    --sound-profile MuseSounds \
    -o "track/02_主唱.wav" \
    "track/musescore/02_主唱/02_主唱.mscx"

# 步骤 3：后处理放大 +6dB（人声音量低，必须放大）
python -c "
import soundfile as sf, numpy as np
data, sr = sf.read('02_主唱.wav')
data = data * 2.0  # +6dB
data = np.clip(data, -0.95, 0.95)
sf.write('02_主唱.wav', data, sr)
"
```


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

## llm 写的主旋律像托dabian
- 改用 minimax-music-api 等技能 生成初稿
minimax-music-api
主唱.prompt.md
标准录音 3.mp3
lyrics.md 
music-3.0-free
[.env](../../../.env)
- 技能audio_chord_recognizer 分离出 vocals.mp3
- 然后转成 md 和json 旋律文件
用我刚刚转成mid 的
vocals.ai.mid （Melodyne 5）
 改编
02_主唱.md
02_主唱.json
你也可以认为是基本照抄。 然后
openutau_lyrics
出 openutau 的歌词

## 