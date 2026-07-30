# AI 音乐助手

基于 AI 的轻量化音乐创作辅助工具。通过哼唱或构思，快速生成和弦、旋律、歌词，并导出为多轨道 MIDI 工程。

---

## 核心定位

> **帮助音乐人更快验证想法、建立音乐工程。帮助普通人快速实现自己的音乐想法。**

三条跑道：
1. **辅助音乐人** — 快速验证灵感，建立工程框架
2. **普通人** — 快速实现自己的音乐想法
3. **探索边界** — 做人类做不了的音乐

---

## 核心链路

```
灵感（哼唱/构思）
    ↓
AI 分析 → 生成和弦/旋律/歌词
    ↓
工程 MD（多轨道、歌词、和弦）
    ↓
持续优化和编辑 → 生成成品
```

---

## 目录结构

```
ai_muice_steper/
├── README.md                 # 本文件
├── .env                      # 环境变量（API 密钥等）  [gitignore]
├── .venv                     # Python 虚拟环境  [gitignore]
├── md/                       # 设计文档与规范
│   ├── currdesign/           # 当前设计
│   │   ├── 总览.md           # 项目总览
│   │   ├── 哼唱一小段的音乐助手设计.md
│   │   ├── 技术栈.md         # 技术架构设计
│   │   ├── 工程MD格式规范.md # 工程文件格式规范
│   │   └── skill.list.md     # 技能列表
│   ├── kb_repo/              # 知识库
│   ├── workflow/             # 工作流程文档
│   └── install/              # 安装指南
│
├── workspace/                # 工作空间（工程文件）  [gitignore]
│   ├── project/              # 歌曲工程
│   │   └── {歌名}/           # 单个歌曲工程
│   │       ├── project.md    # 工程总览
│   │       ├── song_engineer/ # AI 工程聚合
│   │       │   ├── track/    # 轨道设计文档
│   │       │   ├── ai-track/ # AI 生成轨道
│   │       │   └── song_engineer.md
│   │       └── *.mp3         # 原始音频
│   ├── audio_output/         # 音频输出
│   ├── ai_chords/            # AI 和弦分析
│   ├── muse_ai/              # Muse AI 生成
│   └── minimax_music_v3/     # MiniMax 音乐生成
│
├── .workbuddy/               # WorkBuddy 技能配置
└── .cache/                   # 缓存目录 [gitignore]
```

---

## 歌曲工程结构

每个歌曲工程（以「走在」为例）：

```
workspace/project/走在/
├── project.md                # 工程总览
├── 走在_no-watermark.mp3     # 原始音频
└── song_engineer/           # 工程引擎
    ├── song_engineer.md      # 诊断与优化中枢
    ├── song_engineer.json   # 结构化数据
    ├── track/               # 轨道设计文档
    │   ├── 01_和弦.md
    │   ├── 02_主唱.md
    │   └── 03_吉他.md
    ├── ai-track/             # AI 生成轨道
    │   ├── 02_主唱_v4.mid
    │   ├── 02_主唱_v4_lyrics.txt  # OpenUTAU 歌词
    │   ├── 03_吉他.mid
    │   └── ...
    └── res/                  # 资源文件
```

---

## 快速开始

### 1. 环境准备

```bash
# 安装依赖
pip install mido numpy

# MiniMax API（音乐生成）
# 在 .env 中设置 MINIMAX_API_KEY
```

### 2. 创建新工程

```bash
# 在 workspace/project/ 下创建新文件夹
mkdir workspace/project/我的新歌
```

### 3. 核心工作流

| 步骤 | 操作 | 产出 |
|------|------|------|
| 1 | 上传哼唱音频 | 原始音频文件 |
| 2 | AI 旋律分析 | 旋律 MD/JSON |
| 3 | AI 和弦生成 | 和弦 MD |
| 4 | 歌词创作 | 歌词 MD |
| 5 | 多轨编曲 | track/*.md |
| 6 | AI 生成 MIDI | ai-track/*.mid |
| 7 | 导出 OpenUTAU | *.txt 歌词 |

### 4. OpenUTAU 导入

1. 用生成的 MIDI 文件在 OpenUTAU 新建音轨
2. 导入 `.txt` 歌词文件（每行对应一个音符）
3. 选择音色库（使用 `MuseScore_General.sf2`）
4. 渲染人声

---

## 技能列表

| 技能 | 功能 |
|------|------|
| `minimax-music-api` | MiniMax API 音乐生成 |
| `demucs` | 音频轨道分离 |
| `openutau_lyrics` | OpenUTAU 音素歌词生成 |
| `audio_chord_recognizer` | 音频和弦识别 |
| `muse-lyrics-gen` | Muse AI 歌词生成 |

详细见 [md/currdesign/skill.list.md](md/currdesign/skill.list.md)

---

## 工程 MD 格式规范

工程 MD 是项目的**唯一真相源**，聚合和弦、歌词、多轨道、旋律、附件等信息。

格式规范见 [md/currdesign/工程MD格式规范.md](md/currdesign/工程MD格式规范.md)

---

## 相关文档

- [项目总览](md/currdesign/总览.md)
- [哼唱设计](md/currdesign/哼唱一小段的音乐助手设计.md)
- [技术栈](md/currdesign/技术栈.md)
- [工程MD格式规范](md/currdesign/工程MD格式规范.md)
