# MusicGen 音频生成技能

基于 JSON 数据使用 Karplus-Strong 物理建模合成吉他音频。

## 触发词

- 生成 {song}/{track_id} 音频
- 基于 JSON 生成音频
- 吉他合成
- 生成节奏吉他音频

## 使用方法

### 命令行

```bash
python .workbuddy/skills/musicgen-stereo-melody/generate.py <song> <track_id>
python .workbuddy/skills/musicgen-stereo-melody/generate.py 走在 08_节奏吉他
python .workbuddy/skills/musicgen-stereo-melody/generate.py 走在 08
```

### 参数

| 参数 | 说明 | 示例 |
|------|------|------|
| song | 歌曲名 | 走在 |
| track_id | 轨道ID | 08, 8, 08_节奏吉他 |

### 选项

| 选项 | 说明 |
|------|------|
| `--json-only` | 只生成 JSON |
| `--wav-only` | 只生成 WAV |

## 输入

从 `workspace/project/{song}/song_engineer/track/` 目录查找 JSON 文件：
- `08_节奏吉他` → 查找 `08_节奏吉他*.json`
- 支持模糊匹配，自动找最新的修正版本

## 输出

输出到 `workspace/project/{song}/song_engineer/track/musicgen/`：

1. **`{track_id}.json`** - 中间 JSON 元数据
2. **`{track_id}.wav`** - 生成的音频文件

示例：
```bash
python generate.py 走在 08_节奏吉他
# 输出:
# workspace/project/走在/song_engineer/track/musicgen/08_节奏吉他.json
# workspace/project/走在/song_engineer/track/musicgen/08_节奏吉他.wav
```

## 合成器

使用 **Karplus-Strong 物理建模**：
- 模拟真实吉他琴弦振动
- 支持: 拍弦、勾弦、琶音
- 内置简易混响

## 技术支持

| 技术 | 描述 | 音色特点 |
|------|------|----------|
| 拍弦 | 拇指拍弦 | 快起快落，带噪声 |
| 勾弦 | 手指勾弦 | 自然衰减，谐波丰富 |
| 琶音 | 快速拨弦 | 单音短促 |

## 路径规则

详见 `references/output_format.md`

## 配置

从 `.env` 文件读取 `musicgen` 配置（保留用于未来 MusicGen 模型调用）

```bash
musicgen=facebook/musicgen-stereo-melody
```

## 依赖

```bash
pip install numpy soundfile
```