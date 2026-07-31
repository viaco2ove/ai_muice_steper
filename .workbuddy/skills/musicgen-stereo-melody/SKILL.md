# MusicGen 音频生成技能

基于 HuggingFace MusicGen 模型和 MIDI 数据生成逼真的乐器演奏音频。

## 触发词

- 生成 {song}/{track_id} 音频
- 基于 JSON 生成音频
- musicgen 合成
- 生成吉他/贝斯/鼓音频

## 使用方法

### 命令行

```bash
python .workbuddy/skills/musicgen-stereo-melody/generate.py 走在 08
```

### 参数

| 参数 | 说明 | 示例 |
|------|------|------|
| song | 歌曲名 | 走在 |
| track_id | 轨道ID (支持前导零) | 08, 8, 08_节奏吉他 |

### 选项

- `--model, -m`: 指定 MusicGen 模型
- `--output, -o`: 自定义输出路径

## 输入
例如 
track_id=08_节奏吉他

从 `workspace/project/{song}/song_engineer/track/` 目录查找 JSON 文件：
- `{track_id}.json` 这个文件不能直接用于生成音频！

JSON 格式：

```json
{
  "schema": "track.guitar.v1",
  "track_id": 8,
  "name": "节奏吉他",
  "instrument": "木吉他(钢弦)",
  "tempo": 68,
  "volume": 0.4,
  "notes": [
    {
      "actual": "Eb3",
      "midi": 51,
      "duration": "4分",
      "beat_pos": "1.1.1",
      "velocity": 64,
      "technique": "拍弦",
      "sustain_beats": 3
    }
  ]
}
```

## 输出
例如 
track_id=08_节奏吉他
先输出
```
workspace/project/{song}/song_engineer/track/musicgen/{track_id}.josn
```
这个文件直接用于生成音频！

再输出
```
workspace/project/{song}/song_engineer/track/musicgen/{track_id}.wav
```

## 配置

从 `.env` 文件读取 `musicgen` 配置：

```bash
musicgen=musicgen-stereo-melody-large
```

可用模型：
| 模型 | 参数 | 立体声 | 推荐场景 |
|------|------|--------|----------|
| `facebook/musicgen-stereo-melody` | 300M | ✅ | 快速预览 |
| `facebook/musicgen-melody` | 1.5B | ❌ | 一般生成 |
| `facebook/musicgen-melody-large` | 3.3B | ❌ | 高质量 |
| `facebook/musicgen-stereo-melody-large` | 3.3B | ✅ | **吉他首选** |

## 依赖

```bash
pip install torch transformers soundfile numpy python-dotenv
```
