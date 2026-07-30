# 技能 remix-master：基于 remix.json 的音轨混音

## 问题诊断（为什么"放大主唱没有效果"）

经核查现有代码，根本原因已 100% 确认：

**现有的混音脚本 `synth_multitrack_fs.py` / `synth_full_song_fs.py` 根本不读取真正的主唱干声 wav。** 它们对 `02_主唱` 这条轨是用 FluidSynth 重新合成 `program=54` 的合成音色（见 `synth_multitrack_fs.py:44`），而不是读取 OpenUTAU 导出的真人声干声 `02_主唱.wav`。

证据：
- 真正的 OpenUTAU 主唱干声已存在：`workspace/project/走在/song_engineer/track/02_主唱.wav`（= `ai-track/Export/02_主唱_v4_Vocal.wav`，MD5 三处一致，peak=0.674, rms=0.0422）
- 但全工程搜不到任何混音脚本引用 `02_主唱.wav`，只有 `ust_generator.py` 写出 `.org.wav`（原始备份）
- 两个混音脚本的音量参数（`--vocal-vol`、`TRACKS` 里的 `vol`）都是**硬编码在命令行/源码里**，没有配置文件，改了主唱音量只影响"合成人声"，不影响真正的人声轨
- 因此用户调"放大主唱"时，改的是合成参数或命令行参数，但混进全曲的并不是那条真正的主唱，自然"没有效果"

同时 `remix.json` 当前是空文件 `{}`。

## 解决方案

新建技能 `remix-master`，核心是一个**配置驱动的混音器**：读 `remix.json` 配置每条轨的音量/静音/增益等参数，把**真实干声 wav**（优先）或 MIDI 合成音混合成最终母带。配置即混音，参数全部在 `remix.json` 里，改了立刻重混可见效。

## 技能目录结构

```
.workbuddy/skills/remix-master/
├── SKILL.md              # 技能说明：触发词、配置规范、用法
└── scripts/
    └── remix.py          # 配置驱动混音器（核心脚本）
```

## remix.json 配置规范

位置：`workspace/project/{歌名}/song_engineer/remix.json`（已存在，当前为 `{}`）

schema 设计：

```json
{
  "schema": "remix.v1",
  "song": "走在",
  "bpm": 68,
  "tracks": {
    "02_主唱": {
      "source": "auto",
      "vol": 1.0,
      "gain_db": 3.0,
      "mute": false,
      "pan": 0.0,
      "comment": "放大主唱 -> 调 gain_db 或 vol"
    },
    "01_吉他": { "vol": 0.7, "gain_db": 0.0, "mute": false, "pan": 0.0 },
    "13_轻贝斯": { "vol": 0.5, "gain_db": 0.0, "mute": false },
    "09_和声": { "vol": 0.4, "gain_db": 0.0, "mute": false }
  },
  "master": {
    "normalize": true,
    "target_peak": 0.95,
    "limiter": true,
    "output": "workspace/project/走在/song_engineer/track/full_remix.wav"
  }
}
```

**source 字段（关键，解决"没有效果"问题）**：
- `"auto"`（默认）：优先找 `<track>.wav` 真实干声；找不到则 fallback 到 `<track>.mid` + FluidSynth 合成
- `"wav"`：强制用 wav 干声（必须存在，否则报错跳过）
- `"midi"`：强制用 `<track>.mid` 走 FluidSynth 合成（program/soundfont 从 track json 读）

这样主唱默认就用 `02_主唱.wav`（真人声），调 `gain_db` / `vol` 立刻生效。

**音量参数优先级**：先 `vol`（线性倍率）→ 再 `gain_db`（分贝，`10**(gain_db/20)`），两者相乘。`gain_db=6` 约翻倍，`gain_db=-6` 约减半。`mute=true` 直接跳过该轨。

## remix.py 核心逻辑

1. 解析参数：`--remix <remix.json>`（默认指向走在工程）、`--project`、`--track-dir`
2. 读 `remix.json`；若为空 `{}`，自动扫描 `track-dir` 下的 wav 文件生成默认配置（每条 vol=1.0, gain_db=0）并写回，提示用户编辑后重跑
3. 逐轨处理：
   - 解析 source：wav 优先读 `<track>.wav`（用 soundfile，自动重采样到 44100、转 mono）
   - midi fallback：调 FluidSynth 渲染（复用现有 `synth_multitrack_fs.py` 的渲染逻辑思路，program/sf 从 track json 读）
   - 对齐长度（取最长轨为基准，短的右侧补零）
   - 应用 `vol * 10**(gain_db/20)`，应用 pan（左右声道加权）
4. 叠加所有轨 → 母带处理：normalize 到 target_peak、可选 limiter（硬限幅防爆音）→ 写 output wav（沿用现有"先写 tmp ASCII 再 copy"规避中文路径 libsndfile 问题）
5. 打印每轨贡献（peak/rms/是否用真实wav）+ 最终峰值，让用户清楚"主唱这次真的进去了"

**为什么主唱这次会生效**：`02_主唱` 默认 `source=auto` → 读到 `02_主唱.wav`（真人声干声），改 `gain_db: 3.0` 后重混，主唱就在最终 wav 里被放大了。

## SKILL.md 内容要点

- 触发词：混音、remix、放大主唱、调音量、音轨平衡、母带、调音
- 配置规范说明（上面 schema + 字段表）
- 用法示例：
  ```bash
  # 1. 自动生成默认 remix.json
  ./.venv/python.exe .workbuddy/skills/remix-master/scripts/remix.py \
    --project 走在 --init
  # 2. 编辑 remix.json（调 02_主唱 gain_db: 3.0）
  # 3. 重混
  ./.venv/python.exe .workbuddy/skills/remix-master/scripts/remix.py \
    --project 走在
  # -> full_remix.wav，主唱已放大
  ```
- 明确写清："调主唱音量要改 remix.json 里 02_主唱 的 gain_db 或 vol，然后重跑 remix.py。本技能直接用 02_主唱.wav 真人声干声，不是合成人声。"

## 验证

跑通后对比：
- 改 `02_主唱.gain_db` 前后，`full_remix.wav` 的主唱段（1:14 主歌起）响度应有明显差异
- 脚本日志应显示 `02_主唱` 用的是 `02_主唱.wav`（source=wav）而非 midi 合成

## 不做的事

- 不做 EQ/压缩等高级混音（本技能聚焦音量/静音/pan/母带归一化，简单可控）
- 不改动现有 `synth_multitrack_fs.py`（保留兼容）
- 不改 song_engineer.json（remix.json 独立配置文件，解耦）
