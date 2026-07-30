针对版本：版本:4.7.4.260706075
# MSCX 格式规范完整查阅渠道（MuseScore 原生XML乐谱格式）
- github 代码
https://github.com/musescore/
https://github.com/musescore/MuseScore/tree/main/src/importexport/musicxml

- demo
https://github.com/musescore/MuseScore/tree/main/demos
https://github.com/musescore/MuseScore/blob/main/demos/Dawn.mscx

- 模板
https://github.com/musescore/MuseScore/tree/main/share/templates
https://github.com/musescore/MuseScore/blob/main/share/templates/My_First_Score.mscx
https://github.com/musescore/MuseScore/blob/main/share/templates/04-Solo/01-Guitar/01-Guitar.mscx

## templates 目录结构
01-General
02-Choral
03-Chamber_Music
04-Solo
05-Jazz
06-Popular
07-Band_and_Percussion
08-Orchestral
CMakeLists.txt
Marching_Bass_Drums.drm
Marching_Cymbals.drm
Marching_Snare_Drums.drm
Marching_Tenors.drm
My_First_Score.mscx
categories.json
convert.json
drumset_fr.drm
orchestral.drm

## 一、官方权威文档（优先看）

### 1. 官方手册：文件格式基础说明（中英文）

英文原版（最全，官方唯一正式文档）
https://handbook.musescore.org/en/
https://handbook.musescore.org/customization/templates-and-styles
https://handbook.musescore.org/text/formatting-text#levels-of-formatting
内容：

- 区分 `.mscx`（裸XML文本）与 `.mscz`（zip打包，内含score.mscx+图片资源）
- 说明MSCX仅保存乐谱XML，不存储图片；MSCZ才完整打包素材
- 版本兼容性：根标签 `<museScore version="4.30">` 决定节点字段可用性

### 2. 源码 = 终极完整规范（无官方独立XSD/标准文档，源码是事实标准）

MuseScore 是开源项目，**没有发布独立的XSD校验文件**，所有XML节点、字段、取值规则全部定义在源代码中。
GitHub主仓库：[https://github.com/musescore/MuseScore](https://github.com/musescore/MuseScore)
关键源码目录（解析/写入MSCX的核心逻辑）

1. `src/importexport/musicxml/` XML读写核心
2. `src/libmscore/` 所有音乐元素类（Note/Chord/Lyric/Staff/Measure等）
3. `src/importexport/mscx_io.cpp` MSCX序列化/反序列化代码

查看方式：
任意打开一份`.mscx`，对照源码里的`writeXml()`函数，就能看懂每个标签含义、参数取值范围。

## 二、第三方完整解析文档/工具参考（开发、脚本修改用）

### 1. mscxyz Python库文档（最成熟MSCX操作库，完整梳理XML结构）

仓库：[https://github.com/Josef-Friedrich/mscxyz](https://github.com/Josef-Friedrich/mscxyz)
配套文档：[https://mscxyz.readthedocs.io/](https://mscxyz.readthedocs.io/)
价值：完整枚举所有顶层节点、元数据、音符、歌词、谱表、演奏标记XML结构，附带修改示例（改歌词、移调、批量编辑音符）。

### 2. CSDN 结构化解析文章（中文通俗分层架构）

《Muse文件格式规范解析》
[https://wenku.csdn.net/doc/3hrno955zn](https://wenku.csdn.net/doc/3hrno955zn)
梳理三层架构：XML顶层 → 分谱 → 小节 → 和弦/音符，适合快速看懂文件层级。

### 3. FILExt 格式技术摘要（快速基础定义）

[https://filext.com/zh/wenjian-kuozhan-ming/MSCX](https://filext.com/zh/wenjian-kuozhan-ming/MSCX)
简述MIME类型、文件用途、基础标签结构。

## 三、MSCX 文件最简XML骨架（快速看懂规范结构）

```
<?xml version="1.0" encoding="UTF-8"?>
<museScore version="4.20">
  <Score>
    <!-- 全局元数据：歌名、作者、速度、调号拍号 -->
    <metaTag name="title">曲名</metaTag>
    <Staff id="1">
      <!-- 小节 -->
      <Measure>
        <Chord>
          <Note pitch="60" duration="480"/>
          <!-- 歌词标签，适配你人声MIDI+歌词场景 -->
          <Lyric>字</Lyric>
        </Chord>
      </Measure>
    </Staff>
  </Score>
</museScore>
```

## 四、关键补充说明（重要坑点）

1. **无官方标准化XSD**
MusicXML有行业统一标准；MSCX是MuseScore私有XML，不对外发布正式Schema，源码是唯一权威规范，不同大版本（3/4）节点存在大量字段差异，不互通。
2. mscz = zip包，解压后内部`score.mscx`就是标准MSCX文件。
3. 如果你需求是**MIDI+歌词转乐谱**：
优先用MusicXML交换（通用标准，有完整公开规范），MSCX仅用于MuseScore内部工程读写。
4. 歌词相关节点 `<Lyric>`、滑音、连音、力度标记全部在源码`libmscore`内定义。

## 五、分场景推荐查阅渠道

1. 只是看懂、手动修改mscx：官方中文手册 + mscxyz文档
2. 写程序解析/生成mscx：MuseScore GitHub源码 mscx\_io.cpp
3. 跨软件交换乐谱：放弃MSCX，改用标准MusicXML（有完整公开规范）