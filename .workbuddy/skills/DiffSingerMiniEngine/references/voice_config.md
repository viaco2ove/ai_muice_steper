# DiffSingerMiniEngine — 音色调节指南

本文件说明如何调节 DiffSinger 合成歌声的**音色 / 性格**，按「改哪里」从易到难排列。
全部参数都已接入 `02_主唱.singer.json` 的 `voice_conf` 块（见下文），普通调节只改这个 JSON，不用记环境变量。

---

## 0. 总览：什么在影响音色

| 影响维度 | 改什么 | 难度 | 音色变化幅度 |
|---------|--------|------|------------|
| 整体性格（共振峰/气声/张力/表现力） | `voice_conf` 6 个旋钮 | ★ 改 JSON | 中 |
| 质量 ↔ 速度 | CLI `--steps*` | ★ 改命令行 | 无（仅精度/耗时） |
| 共振峰（旧路径） | `DS_GENDER` 环境变量 | ★ 改环境 | 中（同 gender） |
| 声库（换歌手） | `singer` 字段 / `.env` 的 `singers_path` | ★★ 换资源 | **最大** |
| 扩散深度 | `dsconfig.yaml` 的 `max_depth` | ★★ 改声库配置 | 中（过大→水声/糊） |

> 口诀：**要换人了换声库，要调性格改 voice_conf，要提速降 steps。**

---

## 1. `voice_conf` 块（推荐入口）

位置：`workspace/project/{歌名}/song_engineer/track/singer/{track}.singer.json`
（`02_主唱` 轨即 `02_主唱.singer.json`）

渲染时 `render_singer.py` 自动读同目录下的 `{track}.singer.json`，取 `voice_conf` 作为性格旋钮。
字段**全部可选**，缺省回退官方初值（见下表「默认」列）。

```json
{
  "voice_conf": {
    "gender": 0,
    "expr": 1.0,
    "breathiness": 0.0,
    "voicing": 0.0,
    "tension": 0.0,
    "velocity": 1.0
  }
}
```

### 字段逐项说明

| ----字段 -----  | 模型层 | 范围 | 默认 | 语义 / 调节方向                                                     |
|---------------|--------|------|------|---------------------------------------------------------------|
| `gender`      | acoustic | `-1 ~ +1` | `0`（不写则回退 `DS_GENDER` 环境变量） | **整体压共振峰**：正值=偏实声、变尖锐；负值=偏柔、变浑厚（口腔变“圆”的怪厚感）。官方 GENC 曲线。建议 -0.5 |
| `expr`        | pitch | `0 ~ 1+` | `1.0` | **表现力初值**：`0` = 表现力归零（平直、无起伏、机械）；`1.0` = 官方初值；大于 1 更夸张。       |
| `breathiness` | variance | 理论上 clamp `[-96, 0]`（log 域） | `0.0` | **气声量**：越负越虚/越气声。想要明显气声给 `-15 ~ -30`。                         |
| `voicing`     | variance | clamp `[-96, 0]`（log 域） | `0.0` | **发声强度/虚实**：越负越虚（接近气声/耳语感）。                                   |
| `tension`     | variance | clamp `[-10, 10]` | `0.0` | **张力**：正值=更紧绷（咬字更实、更用力）；负值=更松弛（更慵懒/气声感）。                      |
| `velocity`    | acoustic | 默认 `1.0` | `1.0` | **速度感/冲击**：官方常数，一般不必动；调低更柔、调高更冲。                              |

### ⚠️ 关键认知：`breathiness/voicing/tension` 是「初值偏置」不是「硬控」

这三个 variance 字段配合 `retake=true`，作用是**给扩散模型一个整体性格的起点**（bias），
模型在 retake 过程中会在此基础上重新预测曲线。因此：

- 它们决定**整体走向**，不是逐帧精确控制。
- 想要**明显**的气声/紧绷质感，给**偏极值**（如 `breathiness: -20`、`tension: 6`），再渲染听效果。
- 给 `0` 即交回模型自己预测（按声库训练分布走，最自然）。

`gender` / `expr` / `velocity` 是一次性的全局常数，直接乘进模型输入，确定性更强。

---

## 2. CLI 扩散步数（质量 ↔ 速度，不改音色）

`render_singer.py` 的三个 `--steps*` 控制各扩散模型的推理步数：

| 参数 | 默认 | 作用 |
|------|------|------|
| `--steps` | 20 | acoustic 扩散步数（官方 `DiffSingerSteps` 默认） |
| `--steps-pitch` | 10 | pitch 扩散步数（`DiffSingerStepsPitch` 默认） |
| `--steps-variance` | 20 | variance 扩散步数（`DiffSingerStepsVariance` 默认） |

- **调低**（如 `10/5/10`）：渲染更快，但更糙、细节少。
- **调高**（如 `30/15/30`）：更细腻，但更慢。
- ⚠️ **超出训练分布反而变差**：步数不是越大越好，过大会出现「水声 / 发糊」。官方默认就是稳妥值。

其它 CLI 参数：`--bpm`（曲速覆盖，不影响 MIDI 只影响对齐）、`--track`、`--out`、`--lyrics-json`（I/O 路由）、`--plan-only` / `--from-plan`（跳过阶段）。

---

## 3. 旧路径：`DS_GENDER` 环境变量（兼容保留）

`gender` 不写在 `voice_conf` 里时，回退到环境变量 `DS_GENDER`（范围同 gender，`-1 ~ +1`）：

```bash
DS_GENDER=-0.5 .venv/python.exe .workbuddy/skills/DiffSingerMiniEngine/scripts/render_singer.py --project 走在
```

> 优先级：`voice_conf.gender` > `DS_GENDER` > `0`。**新用法直接写 JSON 即可，环境变量仅作兜底。**

---

## 4. 换声库 = 最大音色变化

声库由 `.env` 的 `singers_path` 推导（经 `ds/voicebank.py` 的 `Voicebank.locate()`），
或显式写在 singer.json 的 `singer` 字段：

```json
"singer": "D:\\OpenUtau\\Singers\\Singers\\YunYe_DiffSinger_CE_26.07.16.zip"
```

- 换不同的 DiffSinger ONNX 声库（不同歌手音色）是**改变音色最根本**的手段。
- 声库目录含 `dsconfig.yaml`（见下）、各 `*.onnx`、音素表等，被自动解压使用。

---

## 5. `dsconfig.yaml` 的 `max_depth`（高级）

shallow-diffusion 深度：`depth = min(1.0, max_depth)`（默认 `0.7`）。

- 调大（接近 1.0）：更多浅扩散，更「原声库本色」，但过大会水声/发糊。
- 由声库自带配置，一般**不要手动改**；只有确认水声问题时才考虑下调。

---

## 6. 推荐工作流（先试性格，再正式渲染）

音色调节建议**两步走**，避免每次都从头重算 plan：

```bash
# 第一步：只改 voice_conf（或 steps），先出 plan 不渲染（秒级）
.venv/python.exe .workbuddy/skills/DiffSingerMiniEngine/scripts/render_singer.py \
    --project 走在 --plan-only

# 第二步：确认 plan 没问题，从已有 plan 正式渲染（调好 voice_conf 后只跑这步）
.venv/python.exe .workbuddy/skills/DiffSingerMiniEngine/scripts/render_singer.py \
    --project 走在 --from-plan
```

调 `voice_conf` 时 plan 不变，可反复 `--from-plan` 试不同性格组合，省去对齐/音素计算时间。

---

## 7. 实用配方（直接抄）

> 下列配方把整段 `voice_conf` 替换进 `02_主唱.singer.json` 即可。

**A. 默认 / 自然（官方初值，行为不变）**
```json
"voice_conf": {"gender":0,"expr":1.0,"breathiness":0.0,"voicing":0.0,"tension":0.0,"velocity":1.0}
```

**B. 柔美女声（压共振峰偏柔 + 略带气声）**
```json
"voice_conf": {"gender":-0.5,"expr":1.0,"breathiness":-12.0,"voicing":-6.0,"tension":-2.0,"velocity":1.0}
```

**C. 厚实男声（共振峰偏厚、咬字更实）**
```json
"voice_conf": {"gender":0.4,"expr":1.0,"breathiness":0.0,"voicing":0.0,"tension":3.0,"velocity":1.0}
```

**D. Lo-Fi 慵懒气声（贴合「走在」沙发曲风）**
```json
"voice_conf": {"gender":-0.3,"expr":0.9,"breathiness":-20.0,"voicing":-10.0,"tension":-3.0,"velocity":0.95}
```

**E. 平直机械（表现力归零，适合 demo / 校对音准）**
```json
"voice_conf": {"gender":0,"expr":0.0,"breathiness":0.0,"voicing":0.0,"tension":0.0,"velocity":1.0}
```

---

## 8. 已知坑

- **`gender` 之前是摆设**：早期版本 `singer.json` 里的 `gender` 键代码根本不读（实际只认 `DS_GENDER` 环境变量）。现已接入 `voice_conf.gender`，二者统一。
- **breath/voicing 是负数才有气声**：它们是 log 域、clamp 在 `[-96,0]`，想气声一定要给**负值**，给正值（超出 0）无意义且会被 clamp。
- **steps 不是越大越好**：超出训练分布会水声/糊，官方默认 `20/10/20` 是最稳的。
- **`velocity` 一般不动**：它是官方常数，调它主要改变冲击感而非音色本质。
