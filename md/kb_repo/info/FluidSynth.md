# FluidSynth 和 numpy

无论numpy 还是 FluidSynth 都说粗糙塑料音色，比较适合做验证
# FluidSynth + SoundFont 真实音质合成跑通。

  完成

  关键突破

  你下载的 7 个 SoundFont 解决了最后一块拼图。环境全齐:
  - ✅ libfluidsynth-3.dll(FluidSynth 2.5.7,.env 配置路径)
  - ✅ pyfluidsynth 1.4.0(Python 绑定)
  - ✅ 7 个 SoundFont(GeneralUser GS 默认,还有 FluidR3/Arachno/SGM/Timbres of Heaven)
  - ✅ dll 路径自动从 .env 加到 PATH

  新增脚本

  - synthesize_midi_fs.py -- FluidSynth 单轨合成(真实 SoundFont 采样)
  - synth_full_song_fs.py -- FluidSynth 全曲合成(吉他+人声叠加)

  产物对比(numpy vs FluidSynth)

  ┌──────────────────┬────────────┬──────┬────────┬───────────────────┐
  │       文件       │    后端    │ 大小 │ 采样率 │       音质        │
  ├──────────────────┼────────────┼──────┼────────┼───────────────────┤
  │ 01_吉他.wav      │ numpy      │ 8MB  │ 22050  │ 谐波模拟,失真     │
  ├──────────────────┼────────────┼──────┼────────┼───────────────────┤
  │ 01_吉他_fs.wav   │ FluidSynth │ 16MB │ 44100  │ 真实钢弦吉他采样  │
  ├──────────────────┼────────────┼──────┼────────┼───────────────────┤
  │ full_song.wav    │ numpy      │ 8MB  │ 22050  │ 机器人声          │
  ├──────────────────┼────────────┼──────┼────────┼───────────────────┤
  │ full_song_fs.wav │ FluidSynth │ 16MB │ 44100  │ 真实乐器+人声"喔" │
  └──────────────────┴────────────┴──────┴────────┴───────────────────┘

  全曲 FluidSynth 版详情

  - 时长 3:06,44100Hz/mono,16MB
  - 吉他:program 25(钢弦吉他)SF 采样,vol=0.7
  - 人声:program 85(Voice Oohs"喔"声)SF 采样,vol=1.0
  - RMS 0.143,峰值 0.95(已归一化),各时段能量曲线合理(前奏弱→主歌→副歌强)

  一键命令

  # 全曲(吉他+人声,真实音质)
  ./.venv/python.exe .workbuddy/skills/song_engineer/scripts/synth_full_song_fs.py
  # -> full_song_fs.wav (3:06, 16MB)

  人声的诚实局限

  SoundFont 的 program 85 只能发"喔"声旋律,听不到具体歌词字(那是 TTS/Vocaloid 范畴,SF 做不到)。但比 numpy 版的机器人声真实得多--至少是真人录的合唱"喔"采样,有自然

  一键命令

  # 全曲(吉他+人声,真实音质)
  ./.venv/python.exe .workbuddy/skills/song_engineer/scripts/synth_full_song_fs.py
  # -> full_song_fs.wav (3:06, 16MB)

  人声的诚实局限

  SoundFont 的 program 85 只能发"喔"声旋律,听不到具体歌词字(那是 TTS/Vocaloid 范畴,SF 做不到)。但比 numpy 版的机器人声真实得多--至少是真人录的合唱"喔"采样,有自然的颤音和气声。

  用任意播放器打开 full_song_fs.wav 即可听。吉他轨是真实钢弦吉他音色,人声是"喔"声旋律,两者叠加成完整伴奏+人声。

  如果要听不同 SoundFont 的效果(比如 FluidR3 更饱满、Arachno 更细腻),可以加 --sf "FluidR3_GM2-2.SF2" 参数切换。
