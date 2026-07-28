# MiniMax Music v3 — 《走在》

## 网页端操作步骤

1. 打开 https://www.minimaxi.com/audio/music
2. 模型选择：**Music 3**
3. 歌词框：粘贴 `lyrics_走在.txt` 全部内容
4. 风格框：粘贴 `style_走在.txt` 全部内容
5. 纯音乐：**关闭**（需要人声）
6. 数量：2（生成2首选优）
7. 点击生成

## 文件说明

| 文件 | 用途 | 字符数 |
|------|------|--------|
| `lyrics_走在.txt` | 粘贴到歌词框 | ≤3500 |
| `style_走在.txt` | 粘贴到风格框 | ≤2000 |

## 歌词格式说明

- `[Intro]` `[Verse]` `[Chorus]` 等是结构标签，MiniMax 会识别
- 结构标签后的第一行是编曲说明（MiniMax 会理解为风格提示）
- `…` 前缀表示气声呢喃
- 空行分隔段落

## 风格关键词说明

关键禁用词已写入风格描述：
- `no drums` / `无鼓组`
- `no bass` / `无重贝斯`
- `no electronic` / `无电音`
- `no climax` / `无副歌爆发`

如果生成结果仍有鼓点，可在风格框追加：`absolutely no drums, no percussion, no beat`
