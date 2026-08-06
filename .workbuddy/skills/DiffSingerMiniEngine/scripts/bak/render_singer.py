# -*- coding: utf-8 -*-
"""
DiffSingerMiniEngine v4.1 - 歌声合成（从 lyrics_match.json + DiffSinger音素映射）

修复 (v4→v4.1):
  - 从 lyrics_match.json 读取真实歌词（而非空的ustx）
  - ustx里lyric字段全是'a'占位符，实际歌词在 lyrics_clean.txt
  - lyrics_match.json 由本脚本的 --sync 参数生成

依赖:
  python (with: onnxruntime, soundfile, scipy, pypinyin, mido)
  DiffSinger ONNX 模型: assets/acoustic/diffsinger_acoustic.onnx
  DiffSinger 音素字典: assets/dictionary.txt (opencpop-extension)
"""
import sys, os, tempfile, shutil, argparse, json, hashlib
sys.stdout.reconfigure(encoding='utf-8')

import numpy as np, soundfile as sf, scipy.signal as sps
try:
    import onnxruntime as ort
except ImportError:
    ort = None

try:
    from pypinyin import pinyin, Style
except ImportError:
    pinyin = None

SAMPLE_RATE = 44100
VOCODER_SR = 44109.0  # mel fps=344.6, hop=128

# ── 音素映射（DiffSinger官方字典）───────────────────────────────
def _load_phoneme_dict():
    dict_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'dictionary.txt')
    import urllib.request
    if not os.path.exists(dict_path):
        url = "https://raw.githubusercontent.com/openvpi/DiffSinger/main/dictionaries/opencpop-extension.txt"
        try:
            urllib.request.urlretrieve(url, dict_path)
        except:
            pass

    if os.path.exists(dict_path):
        phonemes = set()
        with open(dict_path, encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split('\t')
                if len(parts) == 2:
                    for ph in parts[1].split():
                        phonemes.add(ph)
        all_p = sorted([p for p in phonemes])
        p2id = {'SP': 1}
        for i, ph in enumerate(all_p):
            if ph == 'SP':
                continue
            p2id[ph] = i + 2  # SP=ID1, 其余按字母序
        return p2id

    # 备用
    return {}


def _split_pinyin(p):
    # ü → v (DiffSinger 用 v 表示 ü)
    p = p.replace('ue', 'v').replace('üe', 'v')
    for ini in ['zh', 'ch', 'sh', 'ng']:
        if p.startswith(ini):
            return ini, p[len(ini):]
    for ini in ['b','p','m','f','d','t','n','l','g','k','h','j','q','x','r','y','w','z','c','s']:
        if p.startswith(ini):
            return ini, p[len(ini):]
    return '', p


def lyric_to_phoneme_ids(lyric, p2id):
    """汉字 → phoneme ID 列表。

    策略：一个音符对应一个 token（拼音的韵母，即元音部分）。
    声母对歌声的影响较小，用韵母作为主token即可。
    R/休止 → SP (ID 1)
    """
    if lyric in ('R', 'sp', 'sil', '', '-', '—', '…'):
        return [p2id.get('SP', 1)]

    if pinyin is None:
        return [p2id.get('SP', 1)]

    try:
        py = pinyin(lyric, style=Style.NORMAL)
        if not py or not py[0] or not py[0][0]:
            return [p2id.get('SP', 1)]
        p = py[0][0].lower()
    except:
        return [p2id.get('SP', 1)]

    if not p:
        return [p2id.get('SP', 1)]

    # 取韵母（辅音后面的元音部分）作为主token
    ini, fin = _split_pinyin(p)
    # 用韵母作为token（决定元音音色）
    if fin and fin in p2id:
        return [p2id[fin]]
    elif fin:
        # 特殊韵母处理
        if fin == 'ng':
            return [p2id.get('N', p2id.get('SP', 1))]
        # ue → v
        if fin == 'ue':
            fin = 'v'
        if fin in p2id:
            return [p2id[fin]]
        # hash 兜底
        h = int(hashlib.md5(fin.encode()).hexdigest(), 16)
        return [(h % 62) + 1]
    elif ini and ini in p2id:
        # 无韵母（如单独的辅音）→ 用声母
        return [p2id[ini]]
    else:
        return [p2id.get('SP', 1)]


# ── ONNX模型加载 ────────────────────────────────────────────────
def load_models(skill_dir):
    ac_path = os.path.join(skill_dir, 'assets', 'acoustic', 'diffsinger_acoustic.onnx')
    voc_path = os.path.join(skill_dir, 'assets', 'vocoder', 'hifigan_vocoder.onnx')
    opts = ort.SessionOptions()
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    providers = ['CPUExecutionProvider']
    ac = ort.InferenceSession(ac_path, opts, providers=providers)
    voc = ort.InferenceSession(voc_path, opts, providers=providers)
    return ac, voc


def midi_to_hz(midi):
    if midi <= 0:
        return 0.0
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))


# ── 合成核心 ────────────────────────────────────────────────────
def synthesize(ac_sess, voc_sess, midi_notes, lyrics, bpm, p2id):
    resolution = 480  # 固定
    tps = resolution * bpm / 60.0  # ticks per second

    # 构建 token 序列
    # midi_dur 修正系数：实测vocoder输出约=sum(midi_dur)×0.55
    # 需要放大 1/0.55≈1.8 才能对齐实际音符时长
    MIDI_DUR_SCALE = 1.8
    tokens, durations, midi_vals = [], [], []
    for nn, ly in zip(midi_notes, lyrics):
        dur_ticks = float(nn['dur'])
        dur_sec = dur_ticks / tps * MIDI_DUR_SCALE  # 秒，修正后
        ids = lyric_to_phoneme_ids(ly, p2id)
        for pid in ids:
            tokens.append(pid)
            durations.append(dur_sec)
            midi_vals.append(nn['note'])

    N = len(tokens)
    if N == 0:
        return np.zeros(int(SAMPLE_RATE), dtype=np.float32)

    # clamp 到有效范围 [1, 62]
    tokens = [max(1, min(62, t)) for t in tokens]
    mn, mx = min(tokens), max(tokens)
    print(f"    tokens: N={N}, range=[{mn},{mx}] (clamped to 1-62)")

    CHUNK = 3
    chunks = []
    for start in range(0, N, CHUNK):
        end = min(start + CHUNK, N)
        chunk_dur = durations[start:end]
        chunk_mid = midi_vals[start:end]
        total_dur = sum(chunk_dur)

        t_tok = np.array([tokens[start:end]], dtype=np.int64)
        t_mid = np.array([chunk_mid], dtype=np.int64)
        t_dur = np.array([chunk_dur], dtype=np.float32)
        t_slur = np.array([[0] * (end - start)], dtype=np.int64)

        _, mel = ac_sess.run(None, {
            'txt_tokens': t_tok,
            'pitch_midi': t_mid,
            'midi_dur': t_dur,
            'is_slur': t_slur,
        })

        nf = mel.shape[1]

        # F0曲线
        # 修复：cum 必须在每个新帧计算时归零，不能跨帧累加
        # 否则 cum 在第一帧处理后就会超过 total_dur，导致后续所有帧 f0=0
        f0 = np.zeros((1, nf), dtype=np.float32)
        if total_dur > 0:
            for i in range(nf):
                t = i * total_dur / nf
                cum = 0.0  # ← 必须在内层循环开始时归零
                for j, d in enumerate(chunk_dur):
                    if cum <= t < cum + d:
                        f0[0, i] = midi_to_hz(chunk_mid[j])
                        break
                    cum += d

        wav = voc_sess.run(None, {'mel_out': mel, 'f0': f0})[0]
        audio = wav.flatten().astype(np.float32)
        chunks.append(audio)
        if start % 30 == 0:
            print(f"      chunk {start:3d}-{end:3d}: mel={nf}f expected={total_dur:.2f}s actual={len(audio)/VOCODER_SR:.2f}s")

    audio = np.concatenate(chunks)

    # 整体时长对齐：拉伸到 MIDI 实际总时长（含休止间隙）
    # MIDI总时长 = 最后一个音符结束时间 = max tick / TPB * 60 / BPM
    expected_total = sum(durations)
    actual_total = len(audio) / VOCODER_SR

    # 算 MIDI 实际结束时间
    tps = 480 * bpm / 60.0
    midi_end = max(nn['tick'] + nn['dur'] for nn in midi_notes) / tps

    ratio = midi_end / actual_total
    print(f"    时长对齐: {actual_total:.1f}s → {midi_end:.1f}s (ratio={ratio:.3f})")
    if 0.5 < ratio < 5.0:
        new_len = int(len(audio) * ratio)
        audio = sps.resample(audio, new_len).astype(np.float32)
        print(f"    拉伸后: {len(audio)/VOCODER_SR:.1f}s")

    # 采样率转换
    if abs(VOCODER_SR - SAMPLE_RATE) < 500:
        target_len = int(len(audio) * SAMPLE_RATE / VOCODER_SR)
        audio = sps.resample(audio, target_len).astype(np.float32)

    # 淡入淡出
    fi = min(int(0.02 * SAMPLE_RATE), len(audio) // 4)
    if fi > 0:
        audio[:fi] *= np.linspace(0, 1, fi)
    fo = min(int(0.05 * SAMPLE_RATE), len(audio) // 4)
    if fo > 0:
        audio[-fo:] *= np.linspace(1, 0, fo)

    return audio


# ── 同步歌词到MIDI ────────────────────────────────────────────────
def sync_lyrics(project, track):
    """从 lyrics_clean.txt + MIDI 生成 lyrics_match.json。"""
    import mido, re
    # scripts/ → DiffSingerMiniEngine/ → skills/ → .workbuddy/ → ai_muice_steper/
    _s = os.path.dirname(os.path.abspath(__file__))
    _d = os.path.dirname(_s)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(_d)))
    project_dir = os.path.join(project_root, "workspace", "project", project)
    midi_path = os.path.join(project_dir, "song_engineer", "track", f"{track}.mid")
    lyrics_path = os.path.join(project_dir, "song_engineer", "ai-track", "minimax", "lyrics_clean.txt")
    out_path = os.path.join(project_dir, "song_engineer", "track", "singer", "lyrics_match.json")

    if not os.path.exists(midi_path):
        print(f"[错误] 未找到MIDI: {midi_path}")
        return None
    if not os.path.exists(lyrics_path):
        print(f"[错误] 未找到歌词: {lyrics_path}")
        return None

    mid = mido.MidiFile(midi_path)
    TPB = mid.ticks_per_beat

    at = 0
    open_notes = {}
    midi_notes = []
    for msg in mid.tracks[1] if len(mid.tracks) > 1 else mid.tracks[0]:
        at += msg.time
        if msg.type == 'note_on' and msg.velocity > 0:
            open_notes[msg.note] = (at, msg.velocity)
        elif (msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0)) and msg.note in open_notes:
            s, v = open_notes.pop(msg.note)
            midi_notes.append({'tick': s, 'note': msg.note, 'dur': at - s, 'vel': v})
    midi_notes.sort(key=lambda x: x['tick'])

    with open(lyrics_path, encoding='utf-8') as f:
        content = f.read()

    all_chars = []
    for line in content.split('\n'):
        line = line.strip()
        if line and not line.startswith('['):
            chars = [c for c in line if '一' <= c <= '鿿']
            all_chars.extend(chars)
        elif '…' in line:
            all_chars.append('…')

    n = len(midi_notes)
    lyrics = ['R'] * n

    # 小节→段落映射
    bar_segs = [
        (5, 12,  0),
        (13, 20, 35),
        (21, 24, 70),
        (25, 32, 70),
        (33, 40, 106),
        (41, 47, 142),
        (48, 52, 180),
    ]

    idx = 0
    for b1, b2, start_idx in bar_segs:
        idxs = [i for i, nn in enumerate(midi_notes)
                if b1 <= nn['tick'] // (TPB * 4) + 1 <= b2]
        if not idxs:
            continue
        seg_chars = all_chars[start_idx:start_idx + 300]
        threshold = 360
        while threshold >= 120:
            cands = [i for i in idxs if midi_notes[i]['dur'] >= threshold]
            if len(cands) >= len(seg_chars):
                break
            threshold -= 60
        if len(cands) < len(seg_chars):
            cands = sorted(idxs, key=lambda i: -midi_notes[i]['dur'])[:len(seg_chars)]
        fill = cands[:len(seg_chars)]
        for i, ch in zip(fill, seg_chars):
            lyrics[i] = ch
        idx += len(seg_chars)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({'midi_notes': midi_notes, 'lyrics': lyrics, 'bpm': 68, 'tpb': TPB}, f, ensure_ascii=False)

    filled = sum(1 for l in lyrics if l != 'R')
    print(f"  同步完成: {filled}/{n} 音符已填词 → {out_path}")
    return out_path


# ── 主入口 ───────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="DiffSingerMiniEngine v4.1")
    parser.add_argument("--project", required=True)
    parser.add_argument("--track", default="02_主唱")
    parser.add_argument("--sync", action="store_true", help="同步歌词到MIDI（首次运行需加此参数）")
    args = parser.parse_args()

    # scripts/ → DiffSingerMiniEngine/ → skills/ → .workbuddy/ → ai_muice_steper/ (项目根)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    skill_dir = os.path.dirname(script_dir)           # DiffSingerMiniEngine/
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(skill_dir)))  # → ai_muice_steper/
    project_dir = os.path.join(project_root, "workspace", "project", args.project)
    singer_dir = os.path.join(project_dir, "song_engineer", "track", "singer")
    os.makedirs(singer_dir, exist_ok=True)
    json_path = os.path.join(singer_dir, "lyrics_match.json")

    print("=" * 60)
    print(f"DiffSingerMiniEngine v4.1 - {args.project} / {args.track}")
    print("=" * 60)

    # 1. 加载音素映射
    print(f"\n[1/5] 加载 DiffSinger 音素映射")
    p2id = _load_phoneme_dict()
    print(f"    音素数: {len(p2id)}, SP=ID {p2id.get('SP', '?')}")

    # 2. 同步歌词（首次）

    if args.sync or not os.path.exists(json_path):
        print(f"\n[2/5] 同步歌词到MIDI")
        sync_lyrics(args.project, args.track)
    else:
        print(f"\n[2/5] 读取 lyrics_match.json")

    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)

    midi_notes = data['midi_notes']
    lyrics = data['lyrics']
    bpm = data.get('bpm', 68)
    filled = sum(1 for l in lyrics if l != 'R')
    print(f"    音符: {len(midi_notes)}, 已填词: {filled}")
    print(f"    BPM: {bpm}")

    # 3. 加载ONNX模型
    print(f"\n[3/5] 加载 ONNX 模型")
    ac, voc = load_models(skill_dir)
    print(f"    ✓ 声学模型 + 声码器")

    # 4. 合成
    print(f"\n[4/5] ONNX 推理")
    audio = synthesize(ac, voc, midi_notes, lyrics, bpm, p2id)
    print(f"    输出: {len(audio)/SAMPLE_RATE:.2f}s  峰值: {float(np.max(np.abs(audio))):.3f}")

    # 5. 保存
    print(f"\n[5/5] 保存音频")
    out_wav = os.path.join(singer_dir, f"{args.track}.wav")
    tmp = os.path.join(tempfile.gettempdir(), f"__singer_{os.getpid()}.wav")
    try:
        sf.write(tmp, audio, SAMPLE_RATE, subtype="PCM_16")
        if os.path.exists(out_wav):
            os.remove(out_wav)
        shutil.copy(tmp, out_wav)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    # 归一化
    peak = float(np.max(np.abs(audio)))
    if peak > 0.891:
        data, sr = sf.read(out_wav)
        data = data * (0.891 / peak)
        sf.write(out_wav, data, sr, subtype="PCM_16")
        print(f"    ✓ 归一化: {peak:.3f} → 0.891")

    print(f"    ✓ 已保存: {out_wav}")
    print(f"\n[完成]")


if __name__ == "__main__":
    main()