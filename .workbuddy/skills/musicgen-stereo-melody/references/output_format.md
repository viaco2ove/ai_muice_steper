# 输出格式模板

## 目录结构

```
workspace/project/{song}/song_engineer/track/musicgen/
├── {track_id}.json          # 中间 JSON (保留完整 notes 数组)
└── {track_id}.wav          # 生成的音频文件
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
  "source": "08_节奏吉他_修正琶音2.json",
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
    },
    {
      "actual": "Eb3",
      "midi": 51,
      "beat_pos": "1.2.1",
      "velocity": 64,
      "technique": "拍弦",
      "duration": "4分"
    }
  ]
}
```

## 字段说明

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

## 路径规则

- **输入 JSON**: `workspace/project/{song}/song_engineer/track/{track_id}.json`
- **输出目录**: `workspace/project/{song}/song_engineer/track/musicgen/`
- **输出 JSON**: `{output_dir}/{track_id}.json`
- **输出 WAV**: `{output_dir}/{track_id}.wav`

## 示例

```bash
# 输入
workspace/project/走在/song_engineer/track/08_节奏吉他.json

# 输出
workspace/project/走在/song_engineer/track/musicgen/08_节奏吉他.json
workspace/project/走在/song_engineer/track/musicgen/08_节奏吉他.wav
```

## 重要原则

1. **保留完整 notes 数组** - 不做任何删减或转换
2. **只添加元数据字段** - `schema`、`source`、`synthesizer`、`reverb`
3. **不修改原始字段** - `notes` 内的每个音符保持原样