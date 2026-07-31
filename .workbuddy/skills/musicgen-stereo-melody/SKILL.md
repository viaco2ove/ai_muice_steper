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

从 `workspace/project/{song}/song_engineer/track/` 目录查找同名 JSON 文件：
- `08_节奏吉他` → 查找 `08_节奏吉他*.json`

## 输出

自动输出到 `workspace/project/{song}/song_engineer/track/musicgen/`：

1. **`{track_id}.json`** - 转换后的可用 JSON（用于生成音频）
2. **`{track_id}.wav`** - 生成的音频文件

示例：
```bash
python generate.py 走在 08_节奏吉他
# 输出:
# workspace/project/走在/song_engineer/track/musicgen/08_节奏吉他.json
# workspace/project/走在/song_engineer/track/musicgen/08_节奏吉他.wav
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
