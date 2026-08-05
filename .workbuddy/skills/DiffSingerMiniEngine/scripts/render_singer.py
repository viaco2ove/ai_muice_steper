# -*- coding: utf-8 -*-
"""
DiffSingerMiniEngine 歌声合成渲染脚本 v2.0（ONNX 推理版）

读 OpenUTAU .ustx 文件，调用 DiffSinger ONNX 模型合成高清歌声。

模型来源: LogiAI10/diffsinger-mobile-onnx (MIT License)
  - assets/acoustic/diffsinger_acoustic.onnx   声学模型
  - assets/vocoder/hifigan_vocoder.onnx        声码器

ONNX 模型接口（已实测）:
  声学模型输入:
    txt_tokens  (1, N) int64  - pinyin token IDs
    pitch_midi  (1, N) int64  - MIDI note (0=rest)
    midi_dur    (1, N) float32 - 每音节时长(秒)
    is_slur     (1, N) int64  - 连音标记(0/1)
  声学模型输出:
    mel_out     (1, n_frames, 80) float32 - 80维mel频谱
  声码器输入:
    mel_out     (1, n_frames, 80) float32
    f0          (1, n_frames) float32     - F0曲线(Hz)
  声码器输出:
    wav_out     (1, n_samples) float32    - 波形

依赖: pip install onnxruntime PyYAML soundfile pypinyin numpy
"""
import sys
import os
import math
import tempfile
import shutil
import argparse

sys.stdout.reconfigure(encoding='utf-8')

import numpy as np
import soundfile as sf
import yaml

try:
    import onnxruntime as ort
    HAS_ORT = True
except ImportError:
    HAS_ORT = False

try:
    from pypinyin import pinyin, Style
    HAS_PYPINYIN = True
except ImportError:
    HAS_PYPINYIN = False

SAMPLE_RATE = 44100

# ── 音素 Token 词汇表（从 pypinyin 构建，0=padding, 1=sp 静音）──
# DiffSinger 的 txt_tokens 是 pinyin 字符串的整数 ID
# 词汇表由 pypinyin NORMAL 格式拼音动态构建
VOCAB = {'<PAD>': 0, 'sp': 1}  # sp=静音/休止


def char_to_token(ch):
    """汉字 → token ID。R/空白 → sp。"""
    if ch in ('R', 'sp', 'sil', '', '…', '—', '-'):
        return VOCAB['sp']
    if not HAS_PYPINYIN:
        # 无 pypinyin：直接用字符的 ord 作为 token（效果差但能跑）
        if ch not in VOCAB:
            VOCAB[ch] = len(VOCAB) + 1
        return VOCAB[ch]
    try:
        py = pinyin(ch, style=Style.NORMAL)
        if not py or not py[0]:
            return VOCAB['sp']
        p = py[0][0]
        if p not in VOCAB:
            VOCAB[p] = len(VOCAB) + 1
        return VOCAB[p]
    except Exception:
        return VOCAB['sp']


# ── ONNX 模型加载 ────────────────────────────────────────────────
def load_models(skill_dir):
    ac_path = os.path.join(skill_dir, 'assets', 'acoustic', 'diffsinger_acoustic.onnx')
    voc_path = os.path.join(skill_dir, 'assets', 'vocoder', 'hifigan_vocoder.onnx')

    sess_opts = ort.SessionOptions()
    sess_opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    providers = ['CPUExecutionProvider']

    ac_sess = ort.InferenceSession(ac_path, sess_opts, providers=providers)
    voc_sess = ort.InferenceSession(voc_path, sess_opts, providers=providers)
    return ac_sess, voc_sess


# ── ustx 解析 ────────────────────────────────────────────────────
def parse_ustx(ustx_path):
    """解析 .ustx，返回 (notes, bpm, resolution)。

    notes: [(position_ticks, duration_ticks, midi_note, lyric_char), ...]
    """
    with open(ustx_path, encoding='utf-8') as f:
        data = yaml.safe_load(f)

    bpm = data.get('bpm', 120)
    resolution = data.get('resolution', 480)
    for tempo in data.get('tempos', []):
        bpm = tempo.get('bpm', bpm)
        break

    notes = []
    for part in data.get('voice_parts', []):
        base_pos = part.get('position', 0)
        for note in part.get('notes', []):
            pos = base_pos + note.get('position', 0)
            dur = note.get('duration', 480)
            tone = note.get('tone', 60)
            lyric = note.get('lyric', 'sp')
            notes.append((pos, dur, tone, lyric))

    notes.sort(key=lambda x: x[0])
    return notes, bpm, resolution


def midi_to_hz(note):
    """MIDI note → Hz。0 = rest → 0 Hz。"""
    if note <= 0:
        return 0.0
    return 440.0 * (2.0 ** ((note - 69) / 12.0))


# ── 主合成逻辑 ───────────────────────────────────────────────────
def synthesize(ac_sess, voc_sess, notes, bpm, resolution):
    """核心 ONNX 推理。

    notes: [(pos_ticks, dur_ticks, midi_note, lyric_char), ...]
    返回: np.array (float32, mono, -1..1)
    """
    tps = resolution * bpm / 60.0  # ticks per second

    # ── 1. 构建 token 序列（跳过连续相同 lyric）──
    tokens = []
    durations = []  # 秒，每音节
    midi_notes = []
    is_slur = []

    prev_lyric = None
    prev_midi = None
    prev_token = None

    for pos, dur, midi, lyric in notes:
        # 跳过连续重复歌词
        if lyric == prev_lyric:
            continue
        prev_lyric = lyric

        dur_sec = dur / tps
        token_id = char_to_token(lyric)

        # slur 标记：歌词相同且音高相同则标记连音
        slur = 1 if (lyric == prev_lyric and midi == prev_midi) else 0

        tokens.append(token_id)
        durations.append(dur_sec)
        midi_notes.append(midi)
        is_slur.append(slur)

        prev_midi = midi
        prev_token = token_id

    N = len(tokens)
    if N == 0:
        return np.zeros(int(SAMPLE_RATE), dtype=np.float32)

    # ── 2. 声学模型推理 ──
    txt_tokens = np.array([[tokens]], dtype=np.int64)
    pitch_midi = np.array([[midi_notes]], dtype=np.int64)
    midi_dur = np.array([[durations]], dtype=np.float32)
    slur_arr = np.array([[is_slur]], dtype=np.int64)

    dec_out, mel_out = ac_sess.run(None, {
        'txt_tokens': txt_tokens,
        'pitch_midi': pitch_midi,
        'midi_dur': midi_dur,
        'is_slur': slur_arr,
    })
    # mel_out: (1, n_frames, 80)
    n_frames = mel_out.shape[1]

    # ── 3. 构建 F0 曲线 ──
    # 每个音符对应的时间段分配 F0
    f0 = np.zeros((1, n_frames), dtype=np.float32)
    total_dur = sum(durations)
    frame_duration = total_dur / n_frames

    for i in range(n_frames):
        t = i * frame_duration
        # 找当前帧落在哪个音符区间
        cum = 0.0
        for j, d in enumerate(durations):
            if cum <= t < cum + d:
                f0[0, i] = midi_to_hz(midi_notes[j])
                break
            cum += d
        # 如果在最后一个音符之后，f0 保持 0（淡出）

    # 简单平滑：插值连接非零段
    for i in range(1, n_frames):
        if f0[0, i] == 0 and f0[0, i - 1] > 0:
            # 找右边非零
            j = i
            while j < n_frames and f0[0, j] == 0:
                j += 1
            if j < n_frames:
                # 线性淡出
                for k in range(i, j):
                    alpha = (k - i + 1) / (j - i + 1)
                    f0[0, k] = f0[0, i - 1] * alpha

    # ── 4. 声码器推理 ──
    wav = voc_sess.run(None, {'mel_out': mel_out, 'f0': f0})[0]
    # wav_out: (1, n_samples), float32, -1..1
    audio = wav.flatten().astype(np.float32)

    # ── 5. 后处理 ──
    # 开头淡入
    fade_in = min(int(0.02 * SAMPLE_RATE), len(audio) // 4)
    if fade_in > 0:
        audio[:fade_in] *= np.linspace(0, 1, fade_in)
    # 末尾淡出
    fade_out = min(int(0.05 * SAMPLE_RATE), len(audio) // 4)
    if fade_out > 0:
        audio[-fade_out:] *= np.linspace(1, 0, fade_out)

    return audio


# ── 主入口 ───────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="DiffSingerMiniEngine 歌声合成 v2.0")
    parser.add_argument("--project", required=True, help="歌曲名")
    parser.add_argument("--track", default="02_主唱", help="音轨名（默认 02_主唱）")
    args = parser.parse_args()

    project = args.project
    track = args.track

    # 路径定位
    script_dir = os.path.dirname(os.path.abspath(__file__))
    skill_dir = os.path.dirname(script_dir)
    track_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(skill_dir))),
        "workspace", "project", project, "song_engineer", "track"
    )
    ai_dir = os.path.join(os.path.dirname(track_dir), "ai-track", "OpenUtau")
    singer_dir = os.path.join(track_dir, "singer")
    singer_dir = os.path.abspath(singer_dir)
    os.makedirs(singer_dir, exist_ok=True)

    ustx_path = os.path.join(ai_dir, f"{track}.ustx")
    if not os.path.exists(ustx_path):
        print(f"[错误] 未找到: {ustx_path}")
        sys.exit(1)

    print("=" * 60)
    print(f"DiffSingerMiniEngine v2.0 - {project} / {track}")
    print("=" * 60)

    # 1. 解析 ustx
    print(f"\n[1/4] 解析 .ustx: {ustx_path}")
    notes, bpm, resolution = parse_ustx(ustx_path)
    print(f"    音符: {len(notes)}  BPM: {bpm:.2f}  分辨率: {resolution}")

    # 2. 加载 ONNX 模型
    print(f"\n[2/4] 加载 ONNX 模型")
    try:
        ac_sess, voc_sess = load_models(skill_dir)
        print(f"    ✓ 声学模型加载成功")
        print(f"    ✓ 声码器加载成功")
    except Exception as e:
        print(f"    [错误] ONNX 模型加载失败: {e}")
        sys.exit(1)

    # 3. 合成
    print(f"\n[3/4] ONNX 推理合成")
    print(f"    vocab size: {len(VOCAB)}  tokens: {list(VOCAB.keys())[:10]}...")
    audio = synthesize(ac_sess, voc_sess, notes, bpm, resolution)
    print(f"    输出: {len(audio)/SAMPLE_RATE:.2f}s  峰值: {float(np.max(np.abs(audio))):.3f}")

    # 4. 保存
    print(f"\n[4/4] 保存音频")
    output_wav = os.path.join(singer_dir, f"{track}.wav")
    tmp = os.path.join(tempfile.gettempdir(), f"__singer_{os.getpid()}.wav")
    try:
        sf.write(tmp, audio, SAMPLE_RATE, subtype="PCM_16")
        if os.path.exists(output_wav):
            os.remove(output_wav)
        shutil.copy(tmp, output_wav)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    print(f"    ✓ 已保存: {output_wav}")
    print(f"\n[完成]")


if __name__ == "__main__":
    main()