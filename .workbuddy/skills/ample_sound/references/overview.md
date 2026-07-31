# Ample Sound 虚拟乐器

## 安装路径

```
D:\Program Files\Ample Sound\
```

## 当前安装内容

- `RectanglesVST3.exe` - VST3 插件宿主（疑似示例/演示程序）
- 无预设库文件 (.nki, .rack)

## 可用音色库

Ample Sound 常见音色库：
- **AGT-III** - 古典吉他
- **ACA** - 原声吉他
- **ASB** - 贝斯系列
- **AML** - 电吉他系列

## 调用方式

### 方式一：通过 DAW 软件

1. 在 DAW (Ableton/FL Studio/Reaper) 中加载 Ample Sound VST
2. 导入 MIDI 文件
3. 渲染导出音频

### 方式二：虚拟 MIDI 路由 (需额外工具)

```
[Python Script] 
    → [虚拟 MIDI 端口] 
    → [DAW + Ample Sound VST] 
    → [音频输出]
```

需要工具：
- `py-virtual-audio-cable` - 虚拟音频线
- `python-rtmidi` - MIDI 输入
- 持续运行的 DAW 进程

### 方式三：命令行自动化

目前 Ample Sound 不支持 headless 命令行调用。

## 结论

**不可行**：Ample Sound 需要 GUI 环境，无法在自动化脚本中直接使用。

**替代方案优先级**：
1. FluidSynth + SoundFont (已配置)
2. MuseScore 渲染 (已配置 musescore_ver=4.7.4)
3. Karplus-Strong 合成器 (CPU 可运行)
4. MusicGen (需要 GPU)