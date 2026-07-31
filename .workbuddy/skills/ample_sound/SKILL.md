---
name: ample_sound
summary: |
  Ample Sound 虚拟乐器音频合成。读取 MIDI 数据，通过 Ample Sound VST 插件渲染生成音频。
  支持吉他、贝斯等乐器的高质量音色。
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
  - ample_path: Ample Sound 安装路径
  - sample_rate: 44100 or 48000
  - bit_depth: 16 or 24
requirements:
  - Ample Sound VST 插件 (本地已安装)
  - MIDI 数据源
  - DAW 软件 (如 Ableton Live, FL Studio)
notes: |
  ## 已知限制

  - Ample Sound 是 VST 插件，需要在 DAW 环境中运行
  - 无法通过命令行直接调用（无 headless 模式）
  - 替代方案：
    1. 使用 py-virtual-audio-cable + python-rtmidi 通过 MIDI 虚拟路由触发 VST
    2. 使用 MuseScore 导出音频 (musescore_ver: 4.7.4)
    3. 使用 FluidSynth + SoundFont (fluid 配置在 .env)
---
