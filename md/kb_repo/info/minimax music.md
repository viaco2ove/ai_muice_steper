# MiniMax Music-3.0 官方上线时间

## 1 正式发布日期

MiniMax 开放平台官方更新日志明确记载：**2026 年 7 月 16 日正式推出 Music-3.0 音乐生成模型**MiniM...。
国内 C 端网页（[https://www.minimaxi.com/audio/music](https://link.wtturl.cn/?target=https%3A%2F%2Fwww.minimaxi.com%2Faudio%2Fmusic&scene=im&aid=582478&lang=zh)）同步在 7 月 18 日开放大众试用、限时免费活动，全网相关测评资讯也集中在 7 月 18 日发布。

## 2 迭代时间线（完整音乐模型谱系）

1. Music 1.5：2025.08
2. Music 2.0：2025.10.29（支持 5 分钟歌曲）MiniM...
3. Music 2.5 / 2.5+：2026.01–03
4. Music 2.6：2026.04
5. Music 3.0：**2026.07.16（最新一代）**MiniM...

## 3 Music 3.0 核心更新（对应歌词补充功能）

1. 新增段落标签配套补充机制：`[Verse]/[Chorus]` 同行标注人声、情绪；
2. 大幅优化中文咬字，支持 Lo-Fi、民谣、极简纯吉他这类小众慵懒曲风；
3. 强化配器禁令识别，更容易锁定 “无鼓、单一木吉他” 这类限制；
4. 加长生成时长，细化段落分层控制，也是你现在在用网页的底层模型。

## 补充小提示

因为上线才 10 天左右，C 端网页的说明文案写得比较简略，

## 
https://platform.minimaxi.com/docs/api-reference/music-generation

curl --request POST \
  --url https://api.minimaxi.com/v1/music_generation \
  --header 'Authorization: Bearer <token>' \
  --header 'Content-Type: application/json' \
  --data '
{
  "model": "music-3.0",
  "prompt": "独立民谣,忧郁,内省,渴望,独自漫步,咖啡馆",
  "lyrics": "[verse]\n街灯微亮晚风轻抚\n影子拉长独自漫步\n旧外套裹着深深忧郁\n不知去向渴望何处\n[chorus]\n推开木门香气弥漫\n熟悉的角落陌生人看",
  "audio_setting": {
    "sample_rate": 44100,
    "bitrate": 256000,
    "format": "mp3"
  }
}
'

model
enum<string>必填
使用的模型名称。可选值：

music-3.0（推荐）：文本生成音乐，仅限 Token Plan 用户和付费用户使用，RPM 为 120
music-2.6：上一代文本生成音乐模型，仅限 Token Plan 用户和付费用户使用，RPM 为 120
music-cover：基于参考音频生成翻唱版本，仅限 Token Plan 用户和付费用户使用，RPM 为 120
music-3.0-free：music-3.0 的限免版本，所有用户可通过 API Key 使用，RPM 为 3
music-2.6-free：music-2.6 的限免版本，所有用户可通过 API Key 使用，RPM 为 3
music-cover-free：music-cover 的限免版本，所有用户可通过 API Key 使用，RPM 为 3
可用选项: music-3.0, music-2.6, music-cover, music-3.0-free, music-2.6-free, music-cover-free

## minimax music web
https://www.minimaxi.com/audio/music
### 歌词输入框 未输入时的提示：
```
在此添加你的歌词，也可以输入 / 查看或插入歌词结构
你可以在 [Intro]、[Verse]、[Chorus] 等结构后补充编曲、人声、情绪等说明
如果未填写歌词，我们将根据曲风为你自动生成
```
其中 “等结构后补充编曲、人声、情绪等说明” 网上没有找到对应例子和说明

### 实际测试效果
```
[Intro]
[吉他分解和弦轻柔开场，木吉他单音泛音余韵，极淡氛围垫音，无歌词]


[Verse 1]
[吉他Cadd9到C7sus4分解节奏型，轻柔留白，人声低输出呢喃，无鼓组]
门虚掩着
风掀了快递
鞋尖沾雨
空调数到七
没起身
窝在花海里
沙发陷着
杯底淡了去
```
出现有时无法控制，有时可以控制，有时对把控制文字也读了的情况

