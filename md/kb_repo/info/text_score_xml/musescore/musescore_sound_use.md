# 乐谱的音色怎么改
# MuseScore 4 改乐谱音色两种方法（适配你装的MuseSounds Core+Guitars Vol.1）
## 前置必做：切换音源为MuseSounds
顶部菜单：**视图 → 播放设置**
配置文件选择 `MuseSounds`，勾选「设为新乐谱默认」，确定。
不切换音源，只会显示老旧MS Basic电子音色。

## 方法1：整行乐器统一改音色（最常用，F10混音器）
1. 快捷键 `F10` 打开混音器面板
2. 找到对应乐器轨道，看 **Sound** 下拉框
3. 点开下拉菜单 → `MuseSounds`
   - MuseSounds Core：管弦、钢琴、打击、合唱
   - Muse Guitars Vol.1：尼龙吉他、钢弦民谣、LP/ST电吉他、电贝斯
4. 点击音色，播放实时生效
> 特点：只改播放声音，五线谱乐器名称、谱号不变。

## 方法2：彻底更换乐谱乐器（快捷键I，改谱面+音色）
1. 快捷键 `I` 打开「乐器」面板
2. 选中当前乐器，点「替换」
3. 在乐器列表选目标乐器（比如原声吉他、电吉他）
4. 确定后：谱号、音域、移调、默认MuseSounds音色全部同步更换
> 适合：整首曲子把钢琴换成吉他这种大范围改动。

## 方法3：同一行乐谱中途切换音色（段落换音色）
比如一段先尼龙吉他，中段换成失真电吉他：
1. 左侧工具栏 → 文本 → 演奏文本
2. 在切换小节处双击添加文本，格式固定：
`Sound:Muse Guitars Vol.1.Acoustic Steel Picked`
完整格式示例：
- 古典尼龙吉他：`Sound:Muse Guitars Vol.1.Acoustic Nylon`
- LP清音电吉他：`Sound:Muse Guitars Vol.1.Electric LP - Clean`
3. 播放读到该文本标记，自动切换音色。

## 常见踩坑解决
1. 混音器下拉看不到Guitars Vol.1
关闭MuseScore完全重启；确认MuseHub内该音色包显示已安装；播放设置音源必须选MuseSounds。
2. 选完还是电子塑料音色
不要选「自动」，手动在MuseSounds分类下点吉他音色，不要停留在MS Basic分类。
3. 推弦、闷音、泛音没效果
只有MuseSounds原生音色支持吉他技法，MS Basic通用GM音色不支持高级演奏法。

# 混音器的选择会保存到
audiosettings.json 而不是 .mscx 里
  01_吉他.mscx          ← 乐谱(音符/调号)，不含音色
  audiosettings.json    ← ★ 音色配置在这！每轨的 MuseSounds 音色
  score_style.mss       ← 谱面样式
  META-INF/container.xml← 清单

## audiosettings.json
首先每个乐谱都要独立的文件夹，用于独立管理audiosettings.json
每个 track 的核心是 in.resourceMeta，MuseSounds 音色的关键字段：
  - type: "muse_sampler_sound_pack"
  - vendor: "MuseSounds"
  - id = museUID（如 "13012"）
  - attributes: museCategory / museName / musePack / museUID / museVendorName / playbackSetupData

  而 partId 要跟 .mscx 里 <Part id="1"> 对应，instrumentId 跟 <Instrument id="guitar-steel"> 对应。

  1. 把 musescore.conf.json 里的音色配置补全（加上 museUID 和 playbackSetupData）
  2. 让生成器除了生成 .mscx，同时生成配套的 audiosettings.json + META-INF/container.xml，这样每轨开箱即用，不用手动在 Mixer 里选

  先查所有音色的 UID 和 playbackSetupData。playbackSetupData 这个字段我需要从库里确认，让我看 .spx 或 SQLite 里有没有：

