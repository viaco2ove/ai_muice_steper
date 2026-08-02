---
name: ample_sound
summary: |
  Ample Sound 虚拟乐器音频合成。使用 dawdreamer headless 渲染 AGML VST3，
  支持吉他、贝斯等乐器的高质量音色（无需 DAW 软件）。
executable: false
triggers:
  - 用 ample 生成音频
  - ample sound 合成
  - Ample 乐器渲染
  - VST 音频生成
inputs:
  - song name
  - track id
outputs:
  - .wav audio file
config:
  - VST_PATH: AGML.vst3 路径（C:/Program Files/Common Files/VST3/AGML.vst3）
  - sample_rate: 44100
requirements:
  - Ample Sound VST 插件 (本地已安装)
  - MIDI 数据源 (JSON 格式)
  - dawdreamer + soundfile
notes: |
  ## 渲染算法 v4（核心逻辑）

  - **拍弦**：使用 MIDI 78 (F#5) 真实拍弦 FX 音效（AGML 4.10 节效果音组），叠加在弦音上
  - **KeySwitch 映射**（AGML 4.2 节）：
    - C0(12)=Sustain, C#0(13)=Natural Harmonic, D0(14)=Palm Mute
    - D#0(15)=Slide In/Out, E0(16)=Legato Slide, F0(17)=Hammer-On/Pull-Off
  - **逐弦时差**：多指/琶音按音高排序后，每弦间隔 18ms（勾弦）/ 30ms（琶音）
  - **力度**：原值×1.1 + 随机±5 起伏，有"人感"
  - **琶音**：保留自然延音，不压缩时长
  - **节拍**：严格按原节拍位置，逐弦时差仅在毫秒级叠加，不推迟任何音符
---
## 文档参考
[Main_Panel_Manual-AGM.pdf.md](../../../md/kb_repo/info/trach_up_level/ample_sound/Main_Panel_Manual-AGM.pdf.md)[Ample Guitar 吉他音源.md](../../../md/kb_repo/info/trach_up_level/Ample%20Guitar%20%E5%90%89%E4%BB%96%E9%9F%B3%E6%BA%90.md)
## 输入

从 `workspace/project/{song}/song_engineer/track/` 目录查找 JSON 文件：
- `08_节奏吉他` → 查找 `08_节奏吉他*.json`
- 支持模糊匹配，自动找最新的修正版本

## 输出

输出到 `workspace/project/{song}/song_engineer/track/ample_sound/`：

1. **`{track_id}.data.json`** - 谱子数据
2. **`{track_id}.json`** - 中间 JSON 元数据
3.**`{track_id}.wav`** - 生成的音频文件
