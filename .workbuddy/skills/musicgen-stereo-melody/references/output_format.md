# 输出格式模板

## 目录结构

```
workspace/project/{song}/song_engineer/track/musicgen/
├── {track_id}.json          # 中间 JSON (保留完整 notes 数组)
├── {track_id}.inputs.md     # MusicGen 文本提示词输入
└── {track_id}.wav           # 生成的音频文件 (可选)
```

## {track_id}.json 模板

```json
{
  "schema": "track.guitar.synth.v1",
  "track_id": 8,
  "name": "节奏吉他",
  "instrument": "木吉他(钢弦)",
  "tempo": 68,
  "volume": 0.4,
  "source": "08_节奏吉他.conf.json",
  "synthesizer": "karplus_strong",
  "reverb": "simple_delay",
  "notes": [
    {
      "actual": "Eb3",
      "midi": 51,
      "beat_pos": "1.1.1",
      "velocity": 64,
      "technique": "拍弦",
      "duration": "4分"
    }
  ]
}
```

## {track_id}.inputs.md 模板

```markdown
# MusicGen 输入提示词

## 基本信息

| 字段 | 值 |
|------|-----|
| 轨道ID | 8 |
| 轨道名称 | 节奏吉他 |
| 乐器 | 木吉他(钢弦) |
| BPM | 68 |
| 时值 | 183.31s |
| 音符数量 | 781 |

## 技术构成

- **四勾**: 408 次 (52.2%)
- **5勾弦**: 171 次 (21.9%)
- **琶音**: 128 次 (16.4%)
- **拍弦**: 74 次 (9.5%)

## 提示词 (Prompt)

```text
acoustic steel string guitar, fingerpicking, gentle chord strumming, slow tempo ballad feel, warm, rhythmic groove
```

## 生成参数

| 参数 | 值 |
|------|-----|
| Duration | 183.31 seconds |
| Sampling Rate | 44100 Hz |
| Model | facebook/musicgen-stereo-melody |
```

## 字段说明

### JSON 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| schema | string | 数据格式版本：`track.guitar.synth.v1` |
| track_id | int | 轨道编号 |
| name | string | 轨道名称 |
| instrument | string | 乐器描述 |
| tempo | int | BPM |
| volume | float | 音量 (0-1) |
| source | string | 原始 JSON 文件名 |
| synthesizer | string | 合成器类型：`karplus_strong` |
| reverb | string | 混响类型：`simple_delay` |
| notes | array | **完整音符数组**，保留原始所有字段 |

### inputs.md 字段

| 字段 | 来源 | 说明 |
|------|------|------|
| 轨道ID | JSON.track_id | 轨道编号 |
| 轨道名称 | JSON.name | 轨道名称 |
| 乐器 | JSON.instrument | 乐器描述 |
| BPM | JSON.tempo | 节拍速度 |
| 时值 | 计算得出 | 总时长（秒） |
| 音符数量 | len(JSON.notes) | 音符总数 |
| 技术构成 | 统计得出 | 各技术出现次数和占比 |
| 提示词 | 组合生成 | MusicGen 文本提示词 |

## 路径规则

- **输入 JSON**: `workspace/project/{song}/song_engineer/track/{track_id}.json`
- **输出目录**: `workspace/project/{song}/song_engineer/track/musicgen/`
- **输出 JSON**: `{output_dir}/{track_id}.json`
- **输出 inputs.md**: `{output_dir}/{track_id}.inputs.md`
- **输出 WAV**: `{output_dir}/{track_id}.wav`

## 示例

```bash
# 输入
workspace/project/走在/song_engineer/track/08_节奏吉他.json

# 输出
workspace/project/走在/song_engineer/track/musicgen/
├── 08_节奏吉他.json       # 中间 JSON
├── 08_节奏吉他.inputs.md  # MusicGen 提示词
└── 08_节奏吉他.wav        # 音频文件
```

## 重要原则

1. **保留完整 notes 数组** - JSON 不做任何删减或转换
2. **只添加元数据字段** - `schema`、`source`、`synthesizer`、`reverb`
3. **不修改原始字段** - `notes` 内的每个音符保持原样
4. **生成 inputs.md** - 自动从 JSON 数据生成 MusicGen 提示词