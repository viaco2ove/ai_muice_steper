使用 dawdreamer + Ample Guitar M Lite VST3

## 预热和生成的裁剪
```
# ═══ 单次渲染：预热段 + 真实段一起加入，渲染后裁掉预热段 ═══
        # 预热段：用前几个音符在 0~WARMUP_OFFSET 内把 VST 状态"唤醒"，
        # 但这段音频最终会被裁掉，不会出现在输出 wav 里。
        WARMUP_OFFSET = 5.5
        sorted_times = sorted(time_groups.keys())

        # 预热音符：铺在 0 ~ WARMUP_OFFSET-0.5 之间（留 0.5s 间隙让尾音自然衰减）
        warmup_times = sorted_times[:5]
        if warmup_times:
            warmup_span = max(0.1, WARMUP_OFFSET - 0.5)
            step = warmup_span / max(1, len(warmup_times))
            for i, t in enumerate(warmup_times):
                wt = i * step
                for note in time_groups[t]:
                    guitar.add_midi_note(note.get("midi", 60), note.get("velocity", 80), wt, 0.5)

        # 真实音符：从 WARMUP_OFFSET 开始
```

## add_midi_note 增加弹奏按键
guitar.add_midi_note(note.get("midi", 60), note.get("velocity", 80), wt, 0.5)
键位，力度，开始时间，持续时间

## 音效键位问题
ai 不知道为什么说在70 -80？
实际是在90-100。

## DawDreamer + AGML 的键位是怎么算的？
在 DawDreamer 里通过 Python 代码操作 VST3 插件时，
传给 add_midi_note(midi_number, ...) 的 midi_number 必须是绝对的 MIDI 音符编号（整数 0~127）。

它和你在 Ample Guitar (AGML) 插件界面里看到的琴键对应关系遵循标准 MIDI 协议：

中央 C (Middle C) 在标准 MIDI 中定义为 C4 = 60。

不同的 DAW 或插件厂商对八度的编号可能略有差异
（例如有的显示 C3 为 60，但 Ample Sound 官方的标准和绝大多数宿主一样，是以 C4 = 60 为标准的）。

你的截图里之所以能点出 Slap 效果，是因为你点中了对应位置的琴键。
如果你要在 Python 代码里精准触发它，只需要查出该键在 0~127 琴键表中的绝对数字。
例如，标准 MIDI 中 C5 = 72，往上推几个半音（如 F#5 或 G#5）
#### 对应的绝对数字就是 78 或 80/81。？？？ 不好意思是错误的
比较坑的地方是 5 ~ 6 ，中间隐藏了一堆高频键位。
实际到了89 才是音效区。89 是弦摩擦音换和弦等时加入可以增加真实感

[Main_Panel_Manual-AGM.pdf.md](Main_Panel_Manual-AGM.pdf.md)
2.15 FX Sound Group
Note	FX Sound	fx_midi

F5	Scratch  89

F#5	Slap  90

G5	Muting  91

G#5	Strum Mute  92

A5	Downstroke Noise 1  93

A#5	Upstroke Noise 1 

B5	Downstroke Noise 2  94

C6	Upstroke Noise 2  95

F6	Hit Top (Open)  96

F#6	Hit Top (Mute)  97

G6	Hit Rim  98

只要把这个绝对数字传给 add_midi_note()，
DawDreamer 就会像你在界面上用鼠标点一样，把这个 MIDI 信号发给 AGML。

## Strummer Mode Toggle
Strummer Mode Toggle 是一个 MIDI 控制器，用于切换弹奏模式。

```
# 按照 F5 = 89 推算，C#6 对应绝对 MIDI 编号为 96
STRUMMER_TOGGLE_MIDI = 96 

# 发送开启指令（力度 127）
guitar.add_midi_note(STRUMER_TOGGLE_MIDI, 127, t + WARMUP_OFFSET - 0.05, 0.05)

# 发送关闭指令（力度设为 30，处于 1-63 区间）
guitar.add_midi_note(STRUMER_TOGGLE_MIDI, 30, t + WARMUP_OFFSET - 0.05, 0.05)
```

一旦开启 Strummer Mode（扫弦模式），插件底部的键盘会被彻底重新划分成 3 个功能完全不同的专属区域。

每个区域的具体按键效果如下：

1. 低音区（Chord Keys / 和弦选定区：约 C1 ~ B2）
作用：用来指定和弦根音与类型（支持单音识别或预设 24 个和弦槽）。

按键效果：当你按下这个区域的键时，本身不会立刻发出单音，而是告诉插件：“接下来要弹某某和弦（比如 C大调 或 Am）”，插件会把这个和弦的按法在虚拟指板上按好。

2. 中高音区（Strum Notes / 扫弦触发与节奏区：约 E3 ~ C4 左右）
作用：用来触发具体的扫弦动作和方向（系统内置了 14 个不同的扫弦动作键、共 28 种玩法）。

按键效果：

Open Down / Open Up（如部分白键）：触发全音或部分弦的上下扫弦。

Muted Down / Muted Up（如部分黑键）：触发闷音扫弦（Palm Mute Strum）。

不同力度和键位组合会直接决定是“向下重扫”、“向上轻挑”还是“切音”。

3. 高音区（SEQ Triggers / 节奏音序触发区：约 C#4 ~ D#4 及其上方）
作用：用来触发面板里预设的伴奏节奏型（SEQ 1 ~ SEQ 8）。

按键效果：按下后，插件会按照内置或你编排好的自动伴奏律动（Loop 节奏型），连贯地自动扫出一串节奏。

## 和弦切换与识别区
1. 低音区：和弦切换与识别区（通常为 C1 ~ B2）
功能：用来决定当前要弹什么和弦。

具体效果：

按下后本身不直接发声，而是让插件在虚拟指板上“按好”对应的和弦。

如果处于 Select 模式：按下 C1 到 B2 的不同白键/黑键，直接切换预设的 24 个和弦槽之一。

如果处于 Detect 模式：你直接在键盘上按一个和弦（比如按 C-E-G），插件会实时识别并切换成该和弦。

2. 中音至高音区：14 种扫弦触发与 28 种技法区（通常在 C3 及以上的主键盘区）
功能：这是用来控制“右手”如何去扫这个和弦的动作区。

具体效果：

Open Down / Open Up（全音上下扫弦）：触发从低音弦到高音弦（或反向）的完整扫弦，不同的键位代表不同的力度分布（如 Full 全扫、Mediant 中频段扫、Treble 高音弦扫）。

Muted Down / Muted Up（闷音上下扫弦）：触发带有 Palm Mute（手掌闷音）效果的扫弦，声音发闷、短促。

分解和弦与单弦触发：某些键位对应特定的单弦拨弦或琶音（如单独拨响 6 弦 E、5 弦 A 等）。

配合不同的按键力度（Velocity），同一个键会衍生出 28 种不同的细节变化（例如轻扫、重扫、切音等）。

3. 特定节奏音序触发区（如 C3, C#3, D#3 等特定音符）
功能：用来触发内置的自动伴奏型（SEQ 1 ~ SEQ 8）。

具体效果：

按下特定的节奏触发键（例如手册中定义的播放 SEQ 1、SEQ 2 等键位），插件就会按照内部编排好的自动伴奏律动（Loop 节奏型），连贯地自动“刷”出一整段吉他伴奏节奏。

在 Ample Sound 的 Strummer 模式中，切换“预设和弦模式 (Select Mode)”与“实时和弦识别模式 (Detect Mode)”主要有两种方式：

1. 鼠标点击面板切换
在插件的 Strummer 面板界面中，直接用鼠标点击和弦设置区域附近的 Chord Mode 切换按钮（通常在面板的左侧或上方），即可在 Select 和 Detect 模式之间来回切换。

2. 通过代码或 MIDI 键盘动态切换（キースイッチ）
如果你想在 Python 代码（如 DawDreamer）或 MIDI 轨道里用代码控制切换，官方定义了一个专用的控制键——D5（根据前面推算的八度与官方手册，其对应的绝对 MIDI 编号通常为 D5 键位）：

切换到 Select 模式：
发送一个 D5 音符，且力度（Velocity）保持在 1 ~ 63 之间。

Python


# 例如用代码切回 Select 模式
guitar.add_midi_note(d5_midi_number, 30, t, duration)
切换到 Detect 模式：
发送一个 D5 音符，且力度（Velocity）保持在 64 ~ 127 之间。

Python


# 例如用代码切换为 Detect（实时按弦识别）模式
guitar.add_midi_note(d5_midi_number, 100, t, duration)


## 开源项目
特点：没有直接的 dawdreamer + Ample Guitar M Lite VST3 开源项目
但有一些  dawdreamer的
https://github.com/DBraun/DawDreamer