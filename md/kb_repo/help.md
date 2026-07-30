# 这是什么？
一个知识库，同时给人和ai 看到。

# 总览

## 这个知识库在做什么？

用 AI 生成音乐有两种路径：

| 路径 | 工具代表 | 产出 | 可编辑性 |
|------|----------|------|----------|
| **AI 直接生成音频** | Suno / Udio / MiniMax Music | MP3/WAV | ❌ 只能重生成，不能逐音符改 |
| **AI 生成乐谱 + 软合成** | LLM + FluidSynth / OpenUTAU | MIDI + JSON + WAV | ✅ 可改音符/歌词/参数 |

本知识库专注于**路径二**：让 AI 生成结构化乐谱（JSON/MIDI），再通过合成引擎渲染成音频，实现人机双向编辑。

## 知识库结构

```
kb_repo/
├── info/
│   ├── 工具分类.md          # 工具全貌：DAW / MuseScore / OpenUTAU / FluidSynth / Polyphone / SoundFont
│   ├── FluidSynth.md        # FluidSynth 详细说明（格式限制、音质、吉他技巧、环境音）
│   ├── 云编曲/云编曲.md     # 云端替代方案：BandLab / Audiotool / 网易天音 / Suno
│   ├── minimax music.md     # MiniMax Music-3.0 API 与歌词控制语法
│   ├── gen_muisc.md         # LLM vs 音频生成模型分类选型
│   ├── wav_to_mid.md        # 音频转 MIDI
│   ├── json_to_music.md     # JSON → 音频合成
│   ├── track_up_level.md    # 轨道升级策略
│   └── text_score_xml/      # MuseScore / 文本格式编曲
├── human_gen/               # 人声合成（OpenUTAU / DiffSinger）
├── 主旋律/                  # 旋律写作：如何好听 + 如何适配 AI 演唱
├── lyric/                   # 歌词设计
└── style/                   # 风格参考
```

## 快速入门

1. **要生成什么？**
   - 完整歌曲音频（不管细节）→ 用 [MiniMax Music](info/minimax%20music.md) 或 [Suno](info/云编曲/云编曲.md)
   - 可编辑乐谱 + 控制细节 → 继续往下

2. **没有本地软件？**
   → 看 [云编曲](info/云编曲/云编曲.md)，BandLab 免费无需安装

3. **有乐谱/MIDI，想渲染音频？**
   → [FluidSynth](info/FluidSynth.md)：加载 SoundFont 渲染 MIDI，音质比 numpy 合成真实

4. **要做带歌词的 AI 人声？**
   → [OpenUTAU + DiffSinger](info/human_gen/openutau/)：输入音符+歌词，导出演唱干声

5. **想自己写旋律？**
   → [如何写出好听的主旋律](info/主旋律/如何写出好听的主旋律.md) + [旋律发展手法](info/主旋律/转音设计.md)

## 核心工具链定位

```
LLM（生成乐谱 JSON）
    ↓
MuseScore（写谱 / 导出 MIDI）
    ↓
┌─────────────────┬──────────────────┐
│  FluidSynth     │  OpenUTAU        │
│  (MIDI + SF2)   │  (音符 + 歌词)   │
│  → 器乐伴奏 WAV │  → 人声干声 WAV  │
└─────────────────┴──────────────────┘
    ↓
DAW 或云工具混音 → 成品
```
