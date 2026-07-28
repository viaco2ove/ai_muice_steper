https://github.com/openutau/OpenUtau/wiki/Getting-Started#windows  
https://github.com/openutau/OpenUtau/wiki/%E6%95%99%E7%A8%8B%E6%B1%87%E6%80%BB-%28%E4%B8%AD%E6%96%87%29

Step 1：装 OpenUTAU

  1. 打开 https://www.openutau.com/  → 点 Download for Windows
  2. 下载 OpenUTAU-win-x64.zip（约 100 MB）
  3. 解压到任意英文路径（强烈建议 D:\OpenUTAU\，不要放在 D:\Users\viaco\桌面\ 之类带中文的路径）
  4. 双击 OpenUTAU.exe 启动

  Step 2：装一个免费中文男歌手

  OpenUTAU 自带没有歌手，要装。推荐：

  ┌──────────────┬──────────────────────┬─────────┬──────────────────────────────────────────────────┐
  │     歌手     │         类型         │  体积   │                       下载                       │
  ├──────────────┼──────────────────────┼─────────┼──────────────────────────────────────────────────┤
  │ MUTA 男      │ 中文男低音，气声自然 │ ~250 MB │ OpenUTAU → Singer → Download Singers → 搜 "MUTA" │
  ├──────────────┼──────────────────────┼─────────┼──────────────────────────────────────────────────┤
  │ 青溯-男      │ 中文男中音，多风格   │ ~200 MB │ 同上                                             │
  ├──────────────┼──────────────────────┼─────────┼──────────────────────────────────────────────────┤
  │ Zhiyu / 知鱼 │ 中文男高音 fallback  │ ~150 MB │ 同上                                             │
  └──────────────┴──────────────────────┴─────────┴──────────────────────────────────────────────────┘

  OpenUTAU 启动后顶部菜单 → Singer → Install Singers to OpenUTAU → 选歌手 → zip 安装。
https://www.zhibin.club/#singers

  找中文男歌手，下载 .zip 后用 OpenUTAU → Singer → Install from Local File。        

  Step 3：渲染主唱

  1. 启动 OpenUTAU
  2. File → Open → 选 D:\Users\viaco\PycharmProjects\ai_muice_steper\workspace\project\走在\song_engineer\track\02_主唱.ust
  3. 顶部面板：Track → Singing track 选你装的歌手（例如 "MUTA 男"）
  4. 中间面板点 Render 按钮（或者菜单 Tools → Render）
  5. 等待 30 秒~3 分钟（看 CPU/歌手包大小）
  6. 输出 wav 默认在 OpenUTAU 同目录的 render/ 文件夹里

  ---
  🔍 渲染前可以预检的点

  在 OpenUTAU 里打开 .ust 后，看一下每个 #NNNN 块的 Lyric 列：
  - ✅ 中文（门、虚、掩、着...）
  - ✅ 没出现 R（气口用了 rest 静音，对的）
  - ⚠️ 如果出现拼音自动转换（如 men、xu），说明 OpenUTAU 没识别中文歌手，要切中文歌手包

  📂 渲染输出后

  把生成好的 wav 文件命名为 02_主唱_ot.wav 放到同目录，然后我们可以再做：

  - 重新混音（替换旧的 02_主唱_fs.wav，去掉 FluidSynth 的机械人声）
  - 跟吉他/和声/贝斯重新合成最终版 full_multitrack.wav

  ---
  如果想我帮忙

  我可以现在写一个：
  - auto_render_check.py：帮你验证 .ust 格式、列字数、估算渲染时长
  - post_render_normalize.py：渲染 wav 出来后自动响度归一化再混音

  要不要在装 OpenUTAU 的同时，让我先帮你做个 UST 自检脚本？

# 要我自己安装并且操作这么麻烦的吗？能不能你安装，并且调用生成
不能。
  
  OpenUTAU 没有 Python SDK，也没有命令行参数模式让你"调命令行直接渲染"。它是一个带 GUI 的 Electron 应用——本质上是个 VST-style
  编辑器，所有交互都是点鼠标。就算我能装，也只能装好让你点。

  你手动点击的步骤（已经最低）

  ┌───────────────────────┬──────────┬──────────────┐
  │         步骤          │   时间   │     难度     │
  ├───────────────────────┼──────────┼──────────────┤
  │ 解压 OpenUTAU         │ 1 分钟   │ 一键         │
  ├───────────────────────┼──────────┼──────────────┤
  │ Singer 菜单搜名字下载 │ 3-5 分钟 │ 选 "MUTA 男" │
  ├───────────────────────┼──────────┼──────────────┤
  │ File → Open 选 .ust   │ 10 秒    │ 找路径       │
  ├───────────────────────┼──────────┼──────────────┤
  │ 选歌手 + Render       │ 30 秒    │ 两个按钮     │
  ├───────────────────────┼──────────┼──────────────┤
  │ 等渲染                │ 1-3 分钟 │ 看进度条     │
  └───────────────────────┴──────────┴──────────────┘

  真实工作量 ≈ 6 分钟，不含下载时间。

# 更多歌手
## 开源免费AI歌手 - OpenUtau DiffSinger
https://audiobar.cn/forum.php?mod=viewthread&tid=585384

https://github.com/xunmengshe/OpenUtau

提供Windows软件和几个模型网盘，其他系统都软件需要去Github下载；
opencpop和夏叶子模型需要使用DIFFS RHY音素器（中文需要转拼音，选中音符按图操作），
其他三个都可以直接使用中文音素器DIFFS ZH

https://www.123pan.com/s/ffA9-ynOn3.html提取码:5555

更多公开模型：https://docs.qq.com/sheet/DQXNDY0pPaEpOc3JN?tab=BB08J2
原神4.2模型：https://pan.ai-hobbyist.org/Models/DiffSinger/%E5%8E%9F%E7%A5%9E

# OpenUtau 歌手（声库）正规下载渠道，分「中文免费商用、DiffSinger AI人声、海外日文音源」，全部无捆绑、适配你的民谣沙发小曲
## 一、国内中文音源（优先，适配中文歌词，免费可发布）
### 1. B站（最推荐，一手官方配布）
关键词搜索：`UTAU中文音源配布` / `DiffSinger 中文声库`
- 绝大多数国产无版权人声（灶歌Upsilon、夏叶子、opencpop、轻治愈民谣女声）作者直接发网盘下载；
- 视频简介自带123盘/百度盘提取码，附试听，**商用规则写得很清楚**；
- 适合你做治愈、沙发民谣温柔人声。

### 2. UTAU中华组Wiki（中文音源汇总站）
收录全部国产CVVC/VCCV中文UTAU声库，每个词条附带**官方下载链接+商用协议**，不会下到改版盗包。

### 3. BowlRoll（国内创作者音源分发站）
https://bowlroll.net/
国内UTAU作者常用配布平台，大量免费中文女声、治愈系声库，直链下载，无需梯子。

### 4. DiffSinger AI人声合集（自然度天花板，替代ACE）
开源中文AI声库清单：
https://docs.qq.com/sheet/DQXNDY0pPaEpOc3JN
包含opencpop、夏叶子、多款治愈民谣女声，AI生成无机械感，**完全免费商用**，OpenUtau原生支持DiffSinger引擎。

## 二、海外日文音源（日系清新、英文民谣）
### 1. UTAU Fandom Wiki（全球最大音源库）
https://utau.fandom.com/wiki/UTAU_Wiki
每款角色（重音Teto、足立レイ等）词条外部链接点`DL`直下，日系温柔女声很多适合治愈曲风。



### 2. MediaFire / OneDrive
海外作者主流网盘，部分需要梯子，适合日系英文民谣声库。

## 三、快速入门推荐音源（直接搜名字下载，适配你的曲风）
### 1）传统UTAU采样人声（轻量化，低配电脑流畅）
1. 灶歌Upsilon：无中之人免费商用，温柔治愈中文女声，沙发小曲首选
2. 夏语遥：老牌清澈中文女声，民谣适配度高
### 2）DiffSinger AI人声（真人质感，推荐主力）
1. Opencpop：开源免费，标准流行/民谣人声
2. 夏叶子：慵懒、轻气声，完美匹配你柔和沙发民谣

## 四、下载+安装极简流程
1. B站/中华组Wiki找到音源，保存网盘压缩包（zip/rar）；
2. 打开OpenUtau → 顶部【工具】→【安装歌手】；



3. 选中压缩包，中文音源编码选 `GB2312`，日文选 `Shift-JIS`；



4. 安装完成后在【工具-歌手】里切换，直接导入人声MIDI+歌词渲染干声WAV。

## 五、避坑重点
1. 拒绝第三方破解资源站（捆绑病毒、修改音源，商用侵权）；
2. 下载前看清作者协议：**标「商用OK」** 才能导出音频对外发布；
3. 区分两种音源：
   - UTAU采样声库：CPU占用低，适合批量渲染；
   - DiffSinger AI声库：人声更自然，但需要Win10+、内存8G以上；
4. 乐器轨道继续用MuseScore General sf2，只把主唱人声交给OpenUtau，整套管线成本最低。
