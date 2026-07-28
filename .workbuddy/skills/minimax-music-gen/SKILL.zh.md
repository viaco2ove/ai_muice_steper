|名字|最小最大音乐生成|
|:----|:----|
|描述|用户想要生成音乐、歌曲或音频轨道时使用。在任何涉及音乐创作、歌曲写作、歌词生成、音频制作或翻唱的请求上触发。当用户提供歌词并希望将其变成歌曲，或描述氛围/场景并希望有背景音乐时，也会触发。支持多语言触发——匹配任何语言中的同义短语。不要用于播放现有文件的音乐、音乐理论问题或在没有生成的情况下进行音乐推荐。|
|许可证|麻省理工学院|
|元数据||

# MiniMax 音乐生成技能

使用MiniMax音乐API生成歌曲（人声或伴奏）。支持两种创作模式：**基础模式**（一句话输入，歌曲输出）和**高级控制**（编辑歌词，优化提示，生成前规划）。

## 先决条件

* **mmx CLI**（必填）：音乐生成使用 `mmx` 命令行工具。**检查是否已安装：**command -v mmx && mmx --version || echo "mmx not found"**安装（需要Node.js）：**npm install -g mmx-cli**认证（仅限首次）：**mmx auth login --api-key <your-minimax-api-key>API 密钥可以从 [MiniMax 平台](https://platform.minimaxi.com/)获取。 凭证保存在 `~/.mmx/credentials.json`中，并在会话之间保持有效。**验证：**mmx quota show

* **音频播放器**（推荐）：`mpv`，`ffplay`，或`afplay`（macOS 内置）用于本地播放。`mpv`因其交互式控制而优先使用。

## 命令行工具

此技能使用`mmx` CLI 生成所有音乐：

* **音乐生成**：`mmx music generate` — 模型：`music-2.6-free`

   * 支持`--lyrics-optimizer`从提示自动生成歌词

   * 支持 `--instrumental` 伴奏曲

   * 支持`--lyrics`用户提供的歌词

   * 结构化参数: `--genre`, `--mood`, `--vocals`, `--instruments`, `--bpm`, `--key`, `--tempo`, `--structure`, `--references`

* **封面**： `mmx music cover` — 模型： `music-cover-free`

   * 通过参考音频 `--audio-file <path>` 或 `--audio <url>`

   * `--prompt`描述目标封面风格

**代理标志**：调用mmx代理时始终添加`--quiet --non-interactive`。

**管道**:

* 声乐：`User description -> mmx music generate --lyrics-optimizer -> MP3`

* 乐器：`User description -> mmx music generate --instrumental -> MP3`

* 封面：`Source audio + style -> mmx music cover -> MP3`

## 存储

所有生成的音乐都会保存到 `~/Music/minimax-gen/`。如果不存在，则创建目录。文件名由时间戳和从提示中派生的简短字符串组成： `YYYYMMDD_HHMMSS_<slug>.mp3`


---
## 语言与互动

从用户的第一条消息中检测用户的语言，并在整段会话中用该语言回应。这适用于所有交互文本、问题、确认和反馈提示。

**面向用户的文本本地化规则**:

* 显示给用户的全部文本——包括预览标签、字段名称、确认信息、状态消息、播放信息、反馈提示，**和提示/描述预览**——必须完全翻译成用户的语言。

* API提示**应始终以英语写入到模型中，以获得最佳生成质量。然而，在向用户预览提示时，显示用户语言的本地化描述，而不是原始的英语提示。英语提示是内部实现细节——用户不需要看到它。**

* 下面的模板是用英文编写的，供参考。在运行时，将每个标签和消息翻译成检测到的用户的语言。

**歌词语言规则**:

* 默认歌词语言 = 用户的语言。一个说中文的用户会得到中文歌词；一个说英文的用户会得到英文歌词。

* 只有在用户**明确**要求时才生成其他语言的歌词。

* 当需要不同语言的歌词时，自然地将它嵌入到提示中的人声或流派描述中。例如，不要简单地添加“带有韩语歌词”，而是使用“有韩国女歌手”或者指定一个包含该语言的流派（例如，“韩流”，“日本摇滚”，“国语歌”，“拉丁流行”）。


---
## 工作流程

### 步骤 0：检测意图

解析用户的消息以确定：

1. **歌曲类别**：人声（有歌词），纯音乐（无歌词）或翻唱

2. **创建模式偏好**：他们提供了详细的需求（高级）还是一个随意的一行代码（基础）？

如果存在歧义，请使用此决策树进行询问：

```plain
Q1: What type of music?
  - Vocal (with lyrics)
  - Instrumental (no vocals)
  - Cover

Q2: Creation mode?
  - Basic — one-line description, auto-generate
  - Advanced — edit lyrics, refine prompt, plan

```


如果用户给出了明确的单行指令，例如 "make me a sad piano piece"，跳过问题 — 推断出器乐 + 基本模式并继续进行。


---
### 步骤 1：基本模式

**目标**：用户提供简短的描述，技能自动生成所有内容，然后调用API。

1. **将描述扩展成一个提示**：将用户的单行扩展成一个丰富的音乐提示。参考本**文档末尾的提示写作指南**附录，了解风格词汇、流派/乐器参考和提示结构。 **API提示应始终用英语**编写，以获得最佳生成质量，无论用户使用什么语言。遵循这个模式：

```plain
A [mood] [BPM optional] [genre] song, featuring [vocal description],
about [narrative/theme], [atmosphere], [key instruments and production].

```


2. **在生成之前向用户显示预览**。将所有标签和提示说明翻译成用户的语言。英文提示仅在调用API时内部使用——用户永远不应看到它。示例模板（英文参考——在运行时本地化所有内容）：

```plain
About to generate:
Type: Vocal / Instrumental
Description: indie folk, melancholy, acoustic guitar, gentle female voice
Lyrics: Auto-generated (--lyrics-optimizer)

Confirm? (press enter to confirm, or tell me what to change)

```


3. **Call mmx**：直接生成音乐。


---
### 步骤 2：高级控制模式

**目标**：用户在生成之前可以完全控制每个参数。

1. **歌词阶段**:

   * 如果用户提供了歌词：以段落标记格式显示，并请求编辑。 最终的歌词将通过 `--lyrics` 传递给 mmx。

   * 如果用户有主题但没有歌词：将使用`--lyrics-optimizer`自动生成。

   * 支持迭代编辑：“更改第二段合唱” -> 只重写那一部分。

   * 用户也可以自己写歌词并提交`--lyrics`.

2. **提示阶段**:

   * 根据歌词的情绪和内容生成一个推荐的提示。

   * 将其呈现为用户可以添加/删除/修改的可编辑标签。

   * 参阅**提示写作指南**附录以获取完整词汇表。

3. **高级规划**（可选，提供但不强制）：

   * 歌曲结构：副歌-副歌-副歌-副歌-桥段-副歌或自定义

   * BPM 建议（在 prompt 中以 tempo 描述符编码）

   * 参考样式：“类似X样式” -> 映射到提示标签

   * 声乐角色描述

4. **最终确认**：显示完整的参数摘要，然后生成。


---
### 步骤 3: 调用 mmx

使用mmx命令行界面生成音乐：

**自动生成歌词的演唱：**

mmx music generate \

  --prompt "<prompt>" \

  --lyrics-optimizer \

  --genre "<genre>" --mood "<mood>" --vocals "<vocal style>" \

  --instruments "<instruments>" --bpm <bpm> \

  --out ~/Music/minimax-gen/<filename>.mp3 \

  --quiet --non-interactive


**人声伴用户提供的歌词：**

mmx music generate \

  --prompt "<prompt>" \

  --lyrics "<lyrics with section markers>" \

  --genre "<genre>" --mood "<mood>" --vocals "<vocal style>" \

  --out ~/Music/minimax-gen/<filename>.mp3 \

  --quiet --non-interactive


**纯音乐（无 vocals）：**

mmx music generate \

  --prompt "<prompt>" \

  --instrumental \

  --genre "<genre>" --mood "<mood>" --instruments "<instruments>" \

  --out ~/Music/minimax-gen/<filename>.mp3 \

  --quiet --non-interactive


使用结构化标志 (`--genre`, `--mood`, `--vocals`, `--instruments`, `--bpm`, `--key`, `--tempo`, `--structure`, `--references`, `--avoid`, `--use-case`) 来给 API 粒度控制，而不是将所有内容都塞进 `--prompt`.

等待时显示进度指示器。典型生成时间为30-120秒。


---
### 步骤 4：回放

经过一代又一代，检测到可用的音频播放器并播放文件。

**检测玩家：**

command -v mpv || command -v ffplay || command -v afplay


**根据检测到的玩家进行游戏（按优先顺序）：**

|玩家|命令|控制|
|:----|:----|:----|
|`mpv`（优先）|`mpv --no-video ~/Music/minimax-gen/<filename>.mp3`|空格键 = 暂停/恢复, q = 退出, 左/右箭头 = 快进|
|`ffplay`|`ffplay -nodisp -autoexit ~/Music/minimax-gen/<filename>.mp3`|q = 退出|
|`afplay`（macOS）|`afplay ~/Music/minimax-gen/<filename>.mp3`|Ctrl+C = 停止|
|未找到|不要尝试播放|仅显示文件路径|

开始播放后，告诉用户（将所有文本本地化）：

```plain
Now playing: <filename>.mp3
Saved to: ~/Music/minimax-gen/<filename>.mp3

```


不要显示播放控件（例如键盘快捷键）——由于播放器在后台运行，这些控件在此环境中无法使用。

如果未找到玩家（本地化所有文本）：

```plain
No audio player detected.
File saved to: ~/Music/minimax-gen/<filename>.mp3
Tip: Install mpv for the best playback experience (brew install mpv).

```



---
### 步骤 5：反馈与迭代

播放后，请收集反馈：

```plain
How was this song?
  1. Love it, keep it!
  2. Not quite, adjust and regenerate
  3. Fine-tune lyrics/style then regenerate
  4. Don't want it, start over

```


根据反馈：

* **满意**：完成。再提一下文件路径。

* **调整和重新生成**：询问需要更改什么（提示？歌词？风格？），应用编辑，重新运行生成。保留旧文件，并使用`_v1`后缀进行比较。

* **微调**：使用当前参数预填，进入高级控制模式。

* **删除并重启**：删除文件，返回步骤0。


---
## 覆盖模式

根据参考音频生成一首歌曲的翻唱版本。模型：`music-cover-free`.

**参考音频要求**：mp3, wav, flac — 时长 6秒到6分钟，最大 50MB。 如果未提供歌词，将通过ASR自动提取原始歌词。

### 工作流程

当用户选择覆盖模式：

1. 请求源音频 — 本地文件路径或URL

2. 询问目标翻唱风格（例如，“原声翻唱，简化版，近距离人声”）

3. 可选地要求自定义歌词或歌词文件

### 命令

**来自本地文件的封面：**

mmx music cover \

  --prompt "<cover style description>" \

  --audio-file <source.mp3> \

  --out ~/Music/minimax-gen/<filename>.mp3 \

  --quiet --non-interactive


**来自URL的封面:**

mmx music cover \

  --prompt "<cover style description>" \

  --audio <source_url> \

  --out ~/Music/minimax-gen/<filename>.mp3 \

  --quiet --non-interactive


**带有自定义歌词（文本）：**

mmx music cover \

  --prompt "<style>" \

  --audio-file <source.mp3> \

  --lyrics "<custom lyrics>" \

  --out ~/Music/minimax-gen/<filename>.mp3 \

  --quiet --non-interactive


**使用自定义歌词（文件）：**

mmx music cover \

  --prompt "<style>" \

  --audio-file <source.mp3> \

  --lyrics-file <lyrics.txt> \

  --out ~/Music/minimax-gen/<filename>.mp3 \

  --quiet --non-interactive


### 可选标志

|旗帜|描述|
|:----|:----|
|`--seed <number>`|随机种子 0-1000000 以确保结果可重复|
|`--channel <n>`|`1` (单声道) 或 `2` (立体声，缺省)|
|`--format <fmt>`|`mp3` (默认), `wav`, `pcm`|
|`--sample-rate <hz>`|采样率（默认：44100）|
|`--bitrate <bps>`|比特率（默认：256000）|

### 经过一代又一代

进行正常播放和反馈流程（步骤4和5）。


---
## 错误处理

|错误|行动|
|:----|:----|
|mmx未找到|`npm install -g mmx-cli`|
|mmx 认证错误（退出代码 3）|`mmx auth login`|
|配额已超过 (退出代码 4)|报告配额限制，建议等待或升级|
|API 超时（退出代码 5）|重试一次，然后报告失败|
|内容过滤（退出代码10）|调整提示以避免过滤内容|
|无效的歌词格式|自动修复章节标记，警告用户|
|未找到音频播放器|保存文件并告诉用户路径，建议安装mpv|
|网络错误|显示错误详情，建议检查连接|


---
## 重要提示

* **切勿复制版权歌曲的歌词。** 在翻唱时，一定要创作与歌曲主题相关的原创歌词。请向用户解释这一点。

* **提示语言**：API提示最好使用英文标签。中文标签也可以接受。混合是允许的。

* **歌词中的段落标记**：API 识别 `[verse]`、`[chorus]`、`[bridge]`、 `[outro]`、`[intro]`。在提供 `--lyrics`时，请始终包含它们。

* **文件管理**：如果`~/Music/minimax-gen/`有超过50个文件，在开始新会话时建议清理

* **结构化参数**：建议使用`--genre`、`--mood`、`--vocals`、`--instruments`， `--bpm`等，而不是将所有内容嵌入到`--prompt`中。这使API具有更好的控制权。

* **通过风格的歌词语言**：当用户想要特定语言的歌词时，通过声乐描述或流派（例如，“日本女歌手”，“国语抒情歌”）来表达，而不是在提示中附加语言指令。


---
## 附录：提示编写指南

参见[references/prompt_guide.md](https://github.com/MiniMax-AI/skills/blob/main/skills/minimax-music-gen/references/prompt_guide.md)以获取完整的提示编写指南， 包括类型/声音/乐器参考和BPM表。


https://platform.minimaxi.com/docs/api-reference/music-generation