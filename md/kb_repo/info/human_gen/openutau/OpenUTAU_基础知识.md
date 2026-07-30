# 中文文档
https://opensynth.miraheze.org/wiki/OpenUTAU/%E4%BD%BF%E7%94%A8%E6%96%B9%E6%B3%95

(首段)
>安装与配置
>界面基本使用
渲染器 
音素器
表情(音符参数)
使用Vogen音源
使用NNSVS音源
使用DiffSinger音源
高级功能
>快捷键

# 简略总结
OpenUTAU 特点 干啥都要重启！点了播放就一直等。不要按暂停不行就重启，不然音色加载就失败。
- OpenUTAU使用“渲染器”作为前端编辑器和后端引擎间的统一接口。
- 音素器可以在音轨窗左侧的混音台选择：也就是语音支持和歌词支持的不同选择不同的因素（CV（默认），ZH CVV（中文扩张整音），ZH CVVC
 ，需要音库自带presamp.ini）， 同时需要音色支持。
- OpenUTAU的“表情”即参数，包括引擎Flag、辅音速度、音量等。通过对参数的编辑，可以实现丰富的效果。
参数分为三种类型：数值型，选项型，曲线型。
参数在钢琴窗底部编辑。左下角切换参数。


# 文档详细
## 渲染器 
{{测试版软件}}

{{翻译自|https://github.com/stakira/OpenUtau/wiki/Getting-Started|OpenUTAU官方文档：Getting-Started}}请注意：本页面是第三方维护的OpenUTAU中文文档，仅供参考。最新资讯请以[http://www.openutau.com/ OpenUTAU官方网站]为准。

本文为OpenUTAU的详细功能参考，面向有UTAU或OpenUTAU基础的用户。初次使用的新用户请前往[[OpenUTAU/指南]]。

== 安装与配置 ==

=== 软件安装 ===
访问[https://github.com/stakira/OpenUtau/releases OpenUTAU发布页面]，Windows系统请下载OpenUtau-win-x64.zip，解压。Mac系统请下载OpenUtau-osx-x64.dmg。Linux系统请下载OpenUtau-linux-x64.tar.gz。

对于Arch Linux或类似系统的用户，可直接安装AUR软件包 [https://aur.archlinux.org/packages/openutau openutau] 。

=== UTAU配置 ===

==== UTAU引擎与拼接器安装 ====
引擎（Resampler）和拼接器（Wavtool）是UTAU协议中音频处理的两大组件。前端编辑器通过调用引擎和拼接器，对音频进行处理。

* 引擎（Resampler），负责将音频采样从原始音高变调到所需的音高，并将用户输入的音符参数（Flag）赋予输出的音频。不同的引擎使用不同的变调算法，主要影响输出的音质。不同的引擎所提供的音符参数也不同。
* 拼接器（Wavtool）负责将引擎输出的音频拼接成连贯的歌声。拼接器对音质的影响较小，部分拼接器在相位对齐等方面进行了优化。

OpenUTAU拥有内置的引擎（wordline-R）和拼接器实现，无需另行安装即可使用UTAU音源。新用户建议使用此内置引擎。如果你需要安装其他引擎和拼接器，请按将引擎exe复制到OpenUTAU目录下的Resamplers文件夹，将拼接器exe复制到Wavtools文件夹。

[[文件:Openutau-引擎安装.png|无框|402x402像素]]

{{模板:OpenUTAU支持的引擎列表}}

{{Hidden|在Mac上使用Windows引擎|# 安装[https://docs.brew.sh/Installation HomeBrew]
# 用以下命令安装[https://github.com/Gcenx/homebrew-wine Wine32on64]<syntaxhighlight lang="bash">
brew tap gcenx/wine
brew install --cask --no-quarantine wine-crossover
</syntaxhighlight>
# 从[https://github.com/stakira/OpenUtau/releases/tag/OpenUtau-Latest OpenUTAU发布页面]下载mac_additional.zip，用sh脚本包装exe引擎。请自行为每个引擎编写sh脚本。
|style = border: 1px solid black; width: 50%;
|headerstyle=background:#ccccff}}
{{Hidden|在Linux上使用Windows引擎|# 安装[https://www.winehq.org/ Wine]
# 打开引擎文件夹（一般是/home/your_username/OpenUtau/Resamplers/）
# 新建一个文本文件。文件名和引擎名称相同，但不需要后缀名。打开，按以下格式编辑：<syntaxhighlight lang="bash">#!/bin/bash
LANG="ja_JP.UTF8" wine "引擎exe绝对路径" "${@,-1}"</syntaxhighlight>
# 运行OpenUTAU
|style = border: 1px solid black; width: 50%;
|headerstyle=background:#ccccff}}

安装后，新建一个音轨，渲染器选择“CLASSIC”，点击齿轮图标，可以在“重采样器”菜单中找到刚才安装的引擎。

[[文件:OpenUTAU-选择引擎.png|400px|在OpenUTAU中选择引擎]]

====UTAU音源安装====
通过“工具→安装歌手”安装音源，支持rar、zip或uar格式的压缩包安装。也可以将压缩包拖入OpenUTAU窗口来安装。

在安装时，可预览音源内的wav文件名和oto.ini。如果文字为乱码，请在右上角选择合适的编码使文字正确显示。

[[文件:OpenUTAU-安装歌手（高级模式）-wav文件名预览.png|400px|安装歌手（高级模式）wav文件名预览]]
[[文件:OpenUTAU-安装歌手（高级模式）-oto预览.png|400px|安装歌手（高级模式） oto预览]]

注意：非日文系统下，不能直接解压音源压缩包，请使用上述方式安装。在日文系统下，或不含日文文件名的压缩文件，你也可以自行解压放入Singers文件夹。如果oto内容乱码，可以在歌手界面重新选择文本文件编码。（参见：[[OpenUTAU/常见问题#为什么要安装音源？/能否与UTAU共用音源文件夹？]]）

==== UTAU插件安装 ====
OpenUTAU支持[[UTAU]]插件的部分功能。将UTAU插件文件夹复制至OpenUTAU目录下的Plugins文件夹中即可。

[[OpenUTAU支持的UTAU插件列表]]

=== Vogen配置 ===
与UTAU音源安装类似，通过“工具→安装歌手”安装音源，选中想要安装的.vogeon文件以安装。OpenUTAU自带Vogen引擎，无需另行安装引擎

在OpenUTAU上使用Vogen音源的方法请见 [[#使用Vogen音源]]

=== NNSVS配置 ===
OpenUTAU NNSVS仅支持Windows系统。以下方法适用于OpenUTAU 0.0.743及以上版本。

==== NNSVS引擎安装 ====
访问[https://github.com/stakira/ENUNU/releases/tag/v0.4.0-openutau ENUNU for OpenUTAU发布页面]，下载ENUNU-0.4.0-Server.zip，解压到任意位置。

NNSVS以本地服务器方式运行，每次启动OpenUTAU前，需先启动NNSVS并保持运行。

* 首次运行时会自动下载NNSVS依赖的Python库，请保持网络畅通，耐心等待。当出现“Started enunu server”时即可使用。
* 电脑中文系统环境下使用日文声库，若终端出现gbk字样的错误，请下载Ntleas等转区软件，使用转区软件转日文环境运行enunu_sever.py。

==== NNSVS音源安装 ====
与UTAU音源安装类似，通过“工具→安装歌手”安装音源。

在OpenUTAU上使用NNSVS音源的方法请见 [[#使用NNSVS音源]]

==界面基本使用==

===文件===

====打开文件====
通过“文件→打开”，或Ctrl+O打开文件，支持.ustx、.ust或.vsqx文件。

通过“文件→导入Midi”打开.mid文件。

如需合并两个文件（在当前文件中追加来自其他文件的音轨），请点击“文件→导入轨道”，支持.ustx、.ust或.vsqx文件。

==== 导入伴奏 ====
通过“文件→导入音频”加载伴奏。支持.wav、.mp3、.flac和.ogg文件。

====保存文件====
OpenUTAU的原生文件格式为.ustx。

通过“文件→保存”或Ctrl+S保存文件。

保存文件后，可通过“文件→另存为ust文件”将每个音轨导出为单独的.ust文件。.ust将导出至和.ustx同一文件夹下。

====导出音频====
保存文件后，可通过“文件→导出wav文件”导出每个音轨为wav文件，将在.ustx文件旁边创建一个文件夹，并导出至该文件夹下。

===节拍与曲速===
点击左上角的节拍与曲速即可修改，暂不支持变速曲。

===音轨===
点击左边栏的+以创建音轨。在音轨上点击以创建区段。双击区段以进入区段编辑音符。

可以在左边栏选择音源、[[OpenUTAU/使用方法#音素器|音素器]]，调节音量和声像。OpenUTAU将记住每个音源上次使用的音素器，并在切换音源时自动切换为该音素器。

=== 音符 ===
左键添加音符，右键删除

双击输入歌词，按tab转到下一个音符

按住Ctrl多选音符，或Ctrl+A全选。键盘上下键按半音上下移动，"Ctrl+上下键"按八度上下移动

==== 批量输入歌词 ====
选中要更改歌词的音符，点击“编辑歌词”

== 渲染器 ==
OpenUTAU是一款开放的歌声合成平台，适配了多种引擎与音源生态。不同的后端引擎，包括拼接引擎和AI引擎都可以使用OpenUTAU编辑器作为其前端。为此，OpenUTAU使用“渲染器”作为前端编辑器和后端引擎间的统一接口。

目前，OpenUTAU拥有以下渲染器：

* CLASSIC：即UTAU引擎。用户可使用Resampler、moresampler、tn_fnds等各种适用于[[UTAU]]的引擎。
* WORDLINE-R：OpenUTAU内置的UTAU音源渲染器实现，运行效率更高，支持曲线参数。
* VOGEN
* ENUNU：即NNSVS
* DIFFSINGER
* VOICEVOX

== 音素器 ==
{{翻译自|https://github.com/stakira/OpenUtau/wiki/Phonemizers|OpenUTAU官方文档：Phonemizers|text=本节}}

音素器（phonemizer）是OpenUTAU的特色功能。在拼接式的歌声合成软件中，一个发音可能由多个采样拼接而成，有[[CVVC]]、[[VCV]]、[[扩张整音]]等拼接方式。在UTAU中，拼接机制完全暴露在用户面前，我们需要手动或使用插件拆音。而在OpenUTAU中，音素器封装了这一过程。我们只需输入歌词即可实时自动拆分。

音素器可以在音轨窗左侧的混音台选择：

[[文件:OpenUTAU-选择音素器.png|无框|530x530像素]]

OpenUTAU的音素器由开源社区的开发者们贡献，目前已经拥有了中文、英文、日文、韩语、葡萄牙语、法语、意大利语、波兰语、俄语、越南语等十余种语言的音素器。

各种OpenUTAU音素器的使用方法，参见[[OpenUTAU/音素器]]

==表情（音符参数）==
OpenUTAU的“表情”即参数，包括引擎Flag、辅音速度、音量等。通过对参数的编辑，可以实现丰富的效果。

参数分为三种类型：数值型，选项型，曲线型。

===编辑表情===
参数在钢琴窗底部编辑。左下角切换参数。

左下角快捷栏可放置5个参数，点击参数名称以进入编辑，点击参数名称左边的下箭头可选择更多参数。

在编辑一个参数时可以把另一个参数作为背景显示，其中深色为当前正在编辑的参数，浅色为背景参数。

[[File:Openutau-曲线型参数编辑.png|无框|305x305像素]]

===配置表情===
OpenUTAU默认支持以下表情：

'''数值型表情'''

仅CLASSIC渲染器支持数值型表情，可手动配置以支持不同UTAU引擎的专属flag
{| class="wikitable"
!名称
!缩写
!说明
!范围
!默认值
|-
|Velocity
|VEL
|辅音速度
|0~200
|100
|-
|Volume
|VOL
|音量
|0~200
|100
|-
|Attack
|ATK
|包络开头音量
|0~200
|100
|-
|Decay
|DEC
|包络末尾音量
|0~100
|0
|-
|Gender
|GEN
|g flag (共振峰移动)
| -100~100
|0
|-
|Breath
|BRE
|B flag (气声)
|0~100
|0
|-
|Lowpass
|LPF
|H flag (低通滤波)
|0~100
|0
|-
|Modulation
|MOD
|移调（合成出的音频音高受原始音频影响的程度）
|0~100
|0
|-
|Alternate
|ALT
|调用同一个oto.ini中的替代采样
|0~16
|0
|-
|Tone shift
|SHFT
|调用不同音阶的采样
| -36~36
|0
|}
'''选项型表情'''

仅CLASSIC渲染器支持选项型表情，可手动配置以支持不同UTAU引擎的专属flag
{| class="wikitable"
!名称
!缩写
!说明
!范围
!默认值
|-
|Voice color
|CLR
|调用音源提供的不同音色采样。可在“工具→歌手→编辑子声库”中配置
|
|
|-
|Resampler engine
|ENG
|调用不同的UTAU引擎
|
|
|}
'''曲线型表情'''

所有渲染器均支持PITD和DYN。WORLDLINE-R、ENUNU和VOGEN支持其余的曲线型表情
{| class="wikitable"
!名称
!缩写
!说明
!范围
!默认值
|-
|Pitch deviation(curve)
|PITD
|音高偏移曲线。可以在钢琴窗中通过4号工具直接绘制
| -1200~1200
|0
|-
|Dynamics(curve)
|DYN
|音量控制曲线。范围对应-24dB~12dB
| -240~120
|0
|-
|gender(curve)
|GENC
|性别
| -100~100
|0
|-
|breathiness(curve)
|BREC
|气声
| -100~100
|0
|-
|tension(curve)
|TENC
|张力
| -100~100
|0
|-
|voicing(curve)
|VOIC
|控制声音的“虚实”或“真声/假声”的比例
|0~100
|0
|}
不同的引擎拥有不同的Flag，所以有时候我们需要修改“表情”的数量与种类。修改的表情配置仅对当前工程文件有效。

====数值型表情====
以下示例把[[Moresampler]]的张力（Mt）Flag添加到OpenUTAU表情配置。“工程→表情”进入配置界面，点击左侧菜单底部的“new expression”。

[[文件:OpenUTAU数值型表情配置.png|无框]]

名称、简称可以随便写，方便记住就行。类型选择“数值”。输入重采样器flag、最小值、最大值、默认值，点击“应用”。

====选项型表情====
以下示例把[[Moresampler]]的音符延长方式（e拉伸，Me循环，留空则自动判断）添加到OpenUTAU表情配置，并将拉伸设为默认值。“工具→表情”进入配置界面，点击左侧菜单底部的“new expression”。

[[文件:OpenUTAU选项型表情配置.png|无框]]

名称、简称可以随便写，方便记住就行。类型选择“选项”。是否重采样器flag打勾。

在“选项值”一栏，列出所有可能的选项值并用逗号分隔。这里的三个选项值分别是"e"、""（留空）、"Me"。其中，第一个选项"e"为默认选项。

点击“应用”。

然后即可在音符编辑窗口看到刚刚添加的表情。

[[文件:OpenUTAU选项型表情编辑界面.png|无框]]

=== 音高编辑 ===
OpenUTAU中提供了多种方式来编辑音高。

各种音高编辑方式的结算顺序为：锚点<手绘曲线<颤音。因此，手绘音高线会覆盖锚点音高线，但不会覆盖颤音。

==== 锚点 ====
类似于UTAU Mode2的锚点音高线。

* 添加控制点：在音高线上单击，即可在该位置创建一个控制点
* 删除控制点：将需要删除的控制点拖动到旁边的控制点上（也可在控制点上右键）
* 右键点击曲线，可修改线形（缓入缓出为S形，缓入为J形，缓出为r形）

==== 手绘曲线 ====
在音符窗口左上角选择第四个工具“绘制音高线工具”。该模式下可直接在钢琴窗上绘制绝对音高，也可在底部的参数栏里面绘制相对音高。

使用鼠标右键，可擦除以这种方式绘制的音高。

[[文件:Openutau-音高编辑-手绘曲线.png|无框]]

注意：

* 手绘音高曲线以相对音高形式存储，不随着音符移动而移动
* Vogen和NNSVS生成的音高曲线以这种方式存储
* 手绘音高曲线目前尚无法整段重置。请检查乐谱正确后再开始绘制

==== 颤音 ====
在音符窗口左上角启用“显示颤音”，然后点击音符右下角的波浪线，即可为当前音符启用颤音。

[[文件:Openutau-启用颤音.png|无框|328x328像素]]

启用颤音后，音符下方显示一个梯形，可通过梯形上的控制点编辑颤音的长度、周期、强度和渐入渐出。

[[文件:Openutau-颤音编辑.png|无框|326x326像素]]

可在“音符设置”中编辑默认颤音预设，为长音符自动启用颤音。

== 使用Vogen音源 ==
在OpenUTAU中使用[[vogen]]音源的方法和使用UTAU音源的方法类似，但需注意：

* 音素器请选择VOGEN ZH（汉语普通话）或VOGEN ZH-YUE（粤语）
* 支持汉字或拼音输入
支持功能：

* 调整音素长度
* 参数 PITD：音高偏差
* 参数 DYN：响度
* 参数 TENC：张力
* 参数 BREC：气声
* 参数 VOIC：发音
* 参数 GENC：性别
*自动音高：请先合成一遍，然后在音符窗口中点击“音符→加载音高渲染结果”。可选择一段单独加载音高，也可加载整个区段。只有合成过的部分才会加载音高。

== 使用NNSVS音源 ==
在OpenUTAU中使用[[NNSVS]]音源的方法和使用UTAU音源的方法类似，但需注意：

* NNSVS以本地服务器方式运行，每次启动OpenUTAU前，需先启动NNSVS并保持运行。
* 音素器请选择NNSVS

支持功能：

*调整音素长度
* 参数： PITD, DYN, TENC, BREC, VOIC, GENC
* 自动音高：请先合成一遍，然后在音符窗口中点击“音符→加载音高渲染结果”。可选择一段单独加载音高，也可加载整个区段。只有合成过的部分才会加载音高。不支持连音符。

== 使用DiffSinger音源 ==
在OpenUTAU中使用[[DiffSinger]]音源的方法和使用UTAU音源的方法类似。

在使用前，请先安装[https://github.com/xunmengshe/OpenUtau/releases/0.0.0.0 声码器]。某些较老的中文音源可能还需要安装[https://github.com/xunmengshe/OpenUtau/releases/0.0.0.0 Rhythmizer]。

支持功能：

* 调整音素长度

* 参数：PITD, DYN, GENC, VELC, CLR, ENE, BREC, TENC, VOIC
** 部分参数需要音源开发者在训练时支持。请参阅音源附带的文档，或向音源开发者询问。
** 如果你需要的参数不默认包含于工程中，请使用“表情→获得渲染器建议的表情”添加到工程中。
* 自动音高：在音符窗口中点击“音符→加载音高渲染结果”。可选择一段单独加载音高，也可加载整个区段。音高渲染可能会较慢，请耐心等待

==高级功能==

===工程模板===
默认情况下，OpenUTAU的表情配置仅对当前工程文件生效。当你配置好表情之后，你不想每一次新建文件之后重新配置一次。除此之外，你可能需要为不同的引擎进行不同的表情配置。此时可以使用“工程模板”功能。

“文件→保存模板”将当前的工程保存为模板。

“文件→从模板新建”来使用模板。

如果将工程模板命名为default，则该模板将在每次新建文件时调用。

一些UTAU引擎的工程模板可以在[https://github.com/oxygen-dioxide/openutau-templates 这里]获取，欢迎贡献更多模板。

=== 界面个性化 ===

==== 主题 ====
OpenUTAU有“亮”和“暗”两种主题色模式，可在“工具→使用偏好”中更改。

在Windows上修改为暗色背景后，如果觉得白色的窗口标题栏与黑色界面不协调，可在“Windows设置→个性化→颜色”中选择一个深色的主题色，并启用“在窗口标题栏显示主题色”。

==== 背景图 ====
OpenUTAU的背景图以音源为单位设置，在音符窗口显示。

设置背景图：点击“工具→歌手→...→选择立绘”，然后找到你想设置的背景图
[[文件:OpenUTAU-设置背景图.png|无框|562x562像素]]

可在“工具→使用偏好”中全局关闭背景图。

如需为某个音源删除背景图，则需找到图片文件并删除，或者打开音源文件夹下的character.yaml，删除以<code>portrait:</code>开头的行。

==快捷键==
{{翻译自|https://github.com/stakira/OpenUtau/wiki/Keyboard-Shortcuts|OpenUTAU官方文档：Keyboard Shortcuts}}
注意：在Mac系统上，Ctrl键为Command键。
===主界面===
{| class="wikitable"
!操作
!快捷键 
|-
|播放/暂停 
|<kbd>Space</kbd>
|-
|跳转到开头
|<kbd>Home</kbd>
|-
|跳转到结尾
|<kbd>End</kbd>
|-
|撤销
|<kbd>Ctrl</kbd> + <kbd>Z</kbd>
|-
|重做
|<kbd>Ctrl</kbd> + <kbd>Y</kbd> / <kbd>Shift</kbd> + <kbd>Ctrl</kbd> + <kbd>Z</kbd>
|-
|剪切
|<kbd>Ctrl</kbd> + <kbd>X</kbd>
|-
|复制
|<kbd>Ctrl</kbd> + <kbd>C</kbd>
|-
|粘贴
|<kbd>Ctrl</kbd> + <kbd>V</kbd>
|-
|全选
| <kbd>Ctrl</kbd> + <kbd>A</kbd>
|-
|取消选择
|<kbd>Ctrl</kbd> + <kbd>D</kbd>
|-
|删除所选区段
|<kbd>Delete</kbd>
|-
|保存
|<kbd>Ctrl</kbd> + <kbd>S</kbd>
|-
| 退出
|<kbd>Alt</kbd> + <kbd>F4</kbd> 
|}

===钢琴窗口===

====文档操作====
{| class="wikitable"
!操作
!快捷键
|-
|撤销
|<kbd>Ctrl</kbd> + <kbd>Z</kbd>
|-
|重做
|<kbd>Ctrl</kbd> + <kbd>Y</kbd> / <kbd>Shift</kbd> + <kbd>Ctrl</kbd> + <kbd>Z</kbd>
|-
|剪切
|<kbd>Ctrl</kbd> + <kbd>X</kbd> 
|-
|复制
|<kbd>Ctrl</kbd> + <kbd>C</kbd>
|-
|粘贴
|<kbd>Ctrl</kbd> + <kbd>V</kbd>
|-
|保存
|<kbd>Ctrl</kbd> + <kbd>S</kbd>
|-
|关闭钢琴窗口
|<kbd>Alt</kbd> + <kbd>F4</kbd>
|}

====编辑操作====
{| class="wikitable"
!操作
!快捷键
|-
|插入新音符
|<kbd>Insert</kbd> 
|-
|删除所选音符
|<kbd>Delete</kbd> / <kbd>Backspace</kbd>
|-
|批量编辑歌词
|<kbd>Enter</kbd> 
|-
|向上移调
|<kbd>↑</kbd>
|-
|向下移调
| <kbd>↓</kbd>
|-
|向上移调八度
|<kbd>Ctrl</kbd> + <kbd>↑</kbd>
|-
|向下移调八度
|<kbd>Ctrl</kbd> + <kbd>↓</kbd>
|-
| 向左移动
|<kbd>Ctrl</kbd> + <kbd>←</kbd>
|-
|向右移动
|<kbd>Ctrl</kbd> + <kbd>→</kbd>
|-
|缩短音符
| <kbd>Alt</kbd> + <kbd>←</kbd> / <kbd>Plus</kbd>
|-
|拉长音符
|<kbd>Alt</kbd> + <kbd>→</kbd> / <kbd>Minus</kbd>
|}

====选择操作====
{| class="wikitable"
!操作
!快捷键
|-
|全选
| <kbd>Ctrl</kbd> + <kbd>A</kbd>
|-
|取消选择
|<kbd>Ctrl</kbd> + <kbd>D / Escape</kbd>
|-
|选择下一个音符
|<kbd>←</kbd>
|-
|选择上一个音符
|<kbd>→</kbd>
|-
|向左扩展选区
| <kbd>Shift</kbd> + <kbd>←</kbd>
|-
|向右扩展选区
|<kbd>Shift</kbd> + <kbd>→</kbd>
|-
|将选区扩展到区段开头
|<kbd>Shift</kbd> + <kbd>Home</kbd>
|-
|将选区扩展到区段结尾
|<kbd>Shift</kbd> + <kbd>End</kbd>
|}

====播放====
{| class="wikitable"
!操作
!快捷键
|-
|播放/暂停
|<kbd>Space</kbd>
|-
|跳转到区段开头
|<kbd>Home</kbd>
|-
|跳转到区段结尾
|<kbd>End</kbd>
|-
|向左移动播放指针
|<kbd>[</kbd>
|-
|向右移动播放指针
|<kbd>]</kbd>
|-
|将播放指针移动到选区开头
|<kbd>Ctrl</kbd> + <kbd>F</kbd> / <kbd>Ctrl</kbd> + <kbd>[</kbd>
|-
| 将播放指针移动到选区结尾 
|<kbd>Ctrl</kbd> + <kbd>]</kbd>
|-
|将播放指针移动到当前视野左端
|<kbd>Shift</kbd> + <kbd>[</kbd>
|-
|将播放指针移动到当前视野右端
|<kbd>Shift</kbd> + <kbd>]</kbd>
|}

====视野滚动====
{| class="wikitable"
!操作
!快捷键
|-
|向左滚动
|<kbd>A</kbd>
|-
|向右滚动
|<kbd>D</kbd>
|-
|向上滚动
|<kbd>Alt</kbd> + <kbd>W</kbd>
|-
|向下滚动
|<kbd>Alt</kbd> + <kbd>S</kbd>
|-
|滚动至选区位置
|<kbd>F</kbd>
|-
|缩小
|<kbd>E</kbd>
|-
|放大
|<kbd>Q</kbd>
|}

====视图元素====
{| class="wikitable"
!操作
!快捷键
|-
|显示波形
|<kbd>W</kbd>
|-
|显示最终音高线
|<kbd>R</kbd>
|-
|显示提示
|<kbd>T</kbd>
|-
|播放音高 
|<kbd>Y</kbd>
|-
|显示颤音
|<kbd>U</kbd>
|-
|显示音高锚点
|<kbd>I</kbd>
|-
|显示音素
|<kbd>O</kbd>
|-
|打开/关闭吸附
|<kbd>P</kbd>
|-
|选择吸附精度
|<kbd>Alt</kbd> + <kbd>P</kbd>
|}

====工具====
{| class="wikitable"
!操作
!快捷键
|-
|选择工具
|<kbd>1</kbd>
|-
|笔工具
|<kbd>2</kbd>
|-
|笔（增强）工具
|<kbd>Ctrl</kbd> + <kbd>2</kbd>
|-
|橡皮工具
|<kbd>3</kbd>
|-
|绘制音高线工具
|<kbd>4</kbd>
|-
|分割工具
|<kbd>5</kbd>
|}

====表情切换====
使用Alt+1至Alt+5，可切换至快捷栏中的第1个至第5个表情

===歌词框 ===
{| class="wikitable"
!操作
!快捷键
|-
|确定
|<kbd>Enter</kbd>
|-
|取消
|<kbd>Escape</kbd>
|-
|跳转到下一个音符
|<kbd>Tab</kbd>
|-
|跳转到上一个音符
|<kbd>Shift</kbd> + <kbd>Tab</kbd>
|}

===批量编辑歌词===
{| class="wikitable"
!操作
!快捷键
|-
|确定
|<kbd>Enter</kbd>
|-
|取消
|<kbd>Escape</kbd>
|}

===歌手界面===
{| class="wikitable"
!Action
!Keys
|-
|上一个
|<kbd>Q</kbd>
|-
|下一个
|<kbd>E</kbd>
|-
|显示全部
|<kbd>F</kbd>
|-
|缩小
|<kbd>W</kbd>
|-
|放大
|<kbd>S</kbd>
|-
|向左滚动视野
|<kbd>A</kbd>
|-
|向右滚动视野
|<kbd>D</kbd>
|}
使用数字键1~5，可分别将原音设定的第1~5条线设置为当前鼠标位置

{{OpenUTAU}}
[[分类:用户文档]]


# 到底电脑还是软件问题
**不是你电脑的问题，也不是你笨，而是 OpenUTAU 这类开源软件的底层逻辑，本来就是“极客折腾型”的。**

如果你觉得它极难用、声音僵硬，真相是“这三要素”合力把你坑了：

---

## 1. 软件模式问题（主要原因：70%）

OpenUTAU 不是一个像剪映、QQ音乐那种“安装打开就能用”的产品，它是一个**开源拼木框架**。

* **商业软件（如 SynthV / ACE）**：像**苹果手机**，软件、引擎、歌手声库全在一个生态里，下载就能唱，AI 自动帮你处理呼吸、转音和咬字。
* **OpenUTAU**：像**组装台式机**。主板（编辑器）、引擎（DiffSinger/Resampler）、音素器（Phonemizer）、声音数据（模型）完全分开。只要其中**任何一个环节配错**（比如用了 DiffSinger 的声库，却挂着传统 UTAU 的拼音转换器），出来的声音就会极其机械、断断续续甚至不出声。

---

## 2. 确实要安装和调整大量东西（20%）

要让 OpenUTAU 稍微好听一点，你必须手动搞定以下这套“插件组合拳”：

1. **音素器（Phonemizer）**：必须针对不同声库选择（比如 `DIFFS ZH` 或 `DIFFS RHY`），选错就瞎唱。
2. **神经网络模型（ONNX 依赖）**：AI 声库需要依赖 ONNX 框架运算。
3. **渲染器与参数**：必须在首选项里调加速倍数（倍数太高音质变差，倍数太低电脑卡死）。
4. **人工画线（Pitch Bend）**：传统的音源如果不人工手动拉颤音、音高过渡线，听起来就是“机械电音”。

---

## 3. 电脑配置的影响（10%）

如果你的电脑没有独立显卡（NVIDIA / AMD），或者在 OpenUTAU 首选项里**没有开启 DirectML / GPU 加速**：

* 电脑会强制用 CPU 计算 AI 模型。
* 结果就是：你改一个音符，电脑卡半天（渲染慢），或者直接报错崩溃。

---

## 总结与建议

| 需求 | 推荐选择 | 体验区别 |
| --- | --- | --- |
| **就想省心写歌、填词即唱** | **Synthesizer V Studio** | 免费版即开即用，AI 转音极其逼真，零配置成本 |
| **喜欢搞研究、玩开源二次开发** | **OpenUTAU + DiffSinger** | 免费但折腾，需要花几小时配置环境、换模型、调参数 |

> **建议：** 别在 OpenUTAU 上继续折腾消耗热情了。直接去下载一个 **Synthesizer V 免费版（Studio Basic）**，配上官方免费的 Lite 歌手，你会在 3 分钟内体验到完全不一样的自然人声。