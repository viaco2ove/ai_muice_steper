# -*- coding: utf-8 -*-
"""
YunYe DiffSinger CE 26.07.16 推理脚本

Pipeline:
  1. lyrics + pinyin → tokens (phoneme IDs) + languages
  2. tokens + durations + spk_emb → acoustic model → mel
  3. mel + f0 → vocoder → waveform

跳过中间模型 (duration/pitch/variance linguistic):
  这些模型的参数(duration/dspitch/variance)需要训练时的校准值，短期内难以正确配置。
  用 MIDI durations 直接驱动 acoustic model。

用法:
  python render_singer_yunye.py --project 走在 --track 02_主唱

需要:
  pip install onnxruntime soundfile scipy PyYAML pypinyin mido numpy
"""
import sys, os, argparse, json, tempfile, shutil
sys.stdout.reconfigure(encoding='utf-8')

import numpy as np, soundfile as sf, scipy.signal as sps
import onnxruntime as ort
import yaml
import mido

try:
    from pypinyin import pinyin, Style
    HAS_PYPINYIN = True
except ImportError:
    HAS_PYPINYIN = False

SAMPLE_RATE = 44109  # vocoder实测: 51200 samples / 100 frames = 86.1fps → sr=51200*86.1≈44109
ACCEPTABLE_SR = 44100  # 写入时目标

# ── 路径 ────────────────────────────────────────────────
SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
ASSET_DIR = os.path.join(SKILL_DIR, '..', 'assets', 'yunye_v2', 'YunYe_DiffSinger_CE_26.07.16')

AC_PATH   = os.path.join(ASSET_DIR, 'acoustic.onnx')
VOC_PATH  = os.path.join(ASSET_DIR, 'dsvocoder', '2601_zhibin_club_ft_pc_nsf_hifigan.onnx')
PH_JSON  = os.path.join(ASSET_DIR, 'phonemes.json')
LANG_JSON = os.path.join(ASSET_DIR, 'languages.json')
DICT_ZH  = os.path.join(ASSET_DIR, 'dsdur', 'dsdict-zh.yaml')
EMB_PATH  = os.path.join(ASSET_DIR, 'yunye.emb')

# ── 加载资源 ──────────────────────────────────────────
def _load():
    global _PH_DATA, _LANG_DATA, _PY2IDS, _SPK_EMB

    # phonemes.json: {'zh/a': 150, 'SP': 4, ...}
    with open(PH_JSON, encoding='utf-8') as f:
        _PH_DATA = json.load(f)

    # languages.json: {'zh': 4, ...}
    with open(LANG_JSON, encoding='utf-8') as f:
        _LANG_DATA = json.load(f)

    # dsdict-zh.yaml: grapheme=pinyin → phonemes=[zh/..., ...]
    with open(DICT_ZH, encoding='utf-8') as f:
        d = yaml.safe_load(f)
    entries = d.get('entries', [])
    _PY2IDS = {}  # pinyin → [(phoneme_id, lang_id), ...]
    zh_id = _LANG_DATA['zh']
    for e in entries:
        py = e.get('grapheme', '')
        phs = e.get('phonemes', [])
        if isinstance(phs, str):
            phs = [phs]
        ids = []
        for ph in phs:
            key = ph  # 已是 'zh/m' 格式
            if key in _PH_DATA:
                ids.append((_PH_DATA[key], zh_id))
        if py and ids:
            _PY2IDS[py] = ids

    # speaker embedding (384,)
    _SPK_EMB = np.fromfile(EMB_PATH, dtype=np.float32).astype(np.float32)
    print(f"  音素表: {len(_PH_DATA)}, 语言: {_LANG_DATA}, 拼音映射: {len(_PY2IDS)}, SpkEmb: {_SPK_EMB.shape}")


_PH_DATA, _LANG_DATA, _PY2IDS, _SPK_EMB = None, None, None, None


def _ensure():
    if _PH_DATA is None:
        _load()


# ── 歌词→token序列 ──────────────────────────────
def _lyric_to_tokens(lyric):
    """单个汉字 → [(phoneme_id, lang_id), ...]"""
    if lyric in ('R', 'sp', 'sil', '', '-', '…', '—', '…'):
        sp_id = _PH_DATA.get('SP', 4)
        zh_id = _LANG_DATA['zh']
        return [(sp_id, zh_id)]
    if not HAS_PYPINYIN:
        return [(_PH_DATA.get('SP', 4), _LANG_DATA['zh'])]
    try:
        py = pinyin(lyric, style=Style.NORMAL)
        p = py[0][0] if py and py[0] else 'sp'
    except:
        return [(_PH_DATA.get('SP', 4), _LANG_DATA['zh'])]
    if not p:
        return [(_PH_DATA.get('SP', 4), _LANG_DATA['zh'])]

    if p in _PY2IDS:
        return _PY2IDS[p]

    # 未找到拼音 → SP
    return [(_PH_DATA.get('SP', 4), _LANG_DATA['zh'])]


def _build_seq(midi_notes, lyrics, bpm):
    """MIDI+歌词 → token序列"""
    tokens, langs, midi_vals = [], [], []
    for nn, ly in zip(midi_notes, lyrics):
        seq = _lyric_to_tokens(ly)
        for pid, lid in seq:
            tokens.append(pid)
            langs.append(lid)
            midi_vals.append(nn['note'])
    return np.array([tokens], np.int64), np.array([langs], np.int64), midi_vals


def midi_to_hz(m):
    if m <= 0: return 0.0
    return 440.0 * (2.0 ** ((m - 69) / 12.0))


# ── 推理 ──────────────────────────────────────────
def synthesize(midi_notes, lyrics, bpm, skip_short=True):
    _ensure()
    res = 480
    tps = res * bpm / 60.0

    tokens, langs, midi_vals = _build_seq(midi_notes, lyrics, bpm)
    N = tokens.shape[1]
    if N == 0:
        return np.zeros(ACCEPTABLE_SR, dtype=np.float32)

    print(f"  tokens: N={N}, range=[{tokens.min()},{tokens.max()}]")

    # durations: 每token的时长(秒) = MIDI音符时长 / phoneme数
    note_dur_ticks = [float(nn['dur']) for nn in midi_notes]
    durations = np.zeros((1, N), dtype=np.float32)
    midi_arr = np.zeros((1, N), dtype=np.int64)
    idx = 0
    for nn in midi_notes:
        seq = _lyric_to_tokens(nn.get('lyric', lyrics[idx] if idx < len(lyrics) else 'R')
        dur_sec = float(nn['dur']) / tps
        for _ in seq:
            if idx < N:
                durations[0, idx] = dur_sec
                midi_arr[0, idx] = nn['note']
                idx += 1

    # 加载模型
    opts = ort.SessionOptions()
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    prov = ['CPUExecutionProvider']

    print(f"  加载模型...")
    ac = ort.InferenceSession(AC_PATH, opts, providers=prov)
    vc = ort.InferenceSession(VOC_PATH, opts, providers=prov)
    print(f"  模型加载完成")

    # speaker embedding: (384,) → broadcast
    spk = _SPK_EMB  # (384,)

    # CHUNK 分块推理（避免 Gather 越界）
    CHUNK = 20
    chunks = []

    for start in range(0, N, CHUNK):
        end = min(start + CHUNK, N)
        t_tok = tokens[:, start:end]
        t_lng = langs[:, start:end]
        t_dur = durations[:, start:end]
        chunk_midi = midi_vals[start:end]
        n_tok = end - start

        # 帧数估算
        total_dur = float(t_dur.sum())
        n_frames = max(10, int(total_dur * 86.1))

        # spk_embed: (1, n_frames, 384)
        spk_exp = np.tile(spk[np.newaxis, np.newaxis, :], (1, n_frames, 1)).astype(np.float32)

        # f0 曲线
        f0 = np.zeros((1, n_frames), dtype=np.float32)
        cum = 0.0
        for i in range(n_frames):
            t = i * total_dur / n_frames
            for j in range(n_tok):
                d = float(t_dur[0, start + j])
                if cum <= t < cum + d:
                    f0[0, i] = midi_to_hz(chunk_midi[j])
                    break
                cum += d
                if cum >= total_dur:
                    break

        # acoustic model
        try:
            mel = ac.run(None, {
                'tokens': t_tok,
                'languages': t_lng,
                'durations': t_dur,
                'f0': f0,
                'breathiness': np.zeros((1, n_frames), dtype=np.float32),
                'voicing': np.ones((1, n_frames), dtype=np.float32),
                'tension': np.zeros((1, n_frames), dtype=np.float32),
                'gender': np.zeros((1, n_frames), dtype=np.float32),
                'velocity': np.ones((1, n_frames), dtype=np.float32),
                'spk_embed': spk_exp,
                'depth': np.array(1.0, dtype=np.float32),
                'steps': np.array(30, dtype=np.int64),
            })[0]
        except Exception as e:
            # 可能是某些参数形状不对，简化重试
            try:
                mel = ac.run(None, {
                    'tokens': t_tok, 'languages': t_lng, 'durations': t_dur,
                    'f0': f0,
                    'breathiness': np.zeros((1, n_frames), dtype=np.float32),
                    'voicing': np.ones((1, n_frames), dtype=np.float32),
                    'tension': np.zeros((1, n_frames), dtype=np.float32),
                    'gender': np.zeros((1, n_frames), dtype=np.float32),
                    'velocity': np.ones((1, n_frames), dtype=np.float32),
                    'spk_embed': np.zeros((1, n_frames, 384), dtype=np.float32),
                    'depth': np.array(0.0, dtype=np.float32),
                    'steps': np.array(0, dtype=np.int64),
                })[0]
            except Exception as e2:
                # 试用最小参数
                mel = ac.run(None, {
                    'tokens': t_tok, 'languages': t_lng, 'durations': t_dur,
                    'f0': f0,
                    'breathiness': np.zeros((1, n_frames), dtype=np.float32),
                    'voicing': np.ones((1, n_frames), dtype=np.float32),
                    'tension': np.zeros((1, n_frames), dtype=np.float32),
                    'gender': np.zeros((1, n_frames), dtype=np.float32),
                    'velocity': np.ones((1, n_frames), dtype=np.float32),
                    'spk_embed': np.zeros((1, n_frames, 384), dtype=np.float32),
                    'depth': np.array(1.0, dtype=np.float32),
                    'steps': np.array(30, dtype=np.int64),
                })[0]

        # vocoder
        wav = vc.run(None, {'mel': mel.astype(np.float32), 'f0': f0.astype(np.float32)})[0]
        audio = wav.flatten().astype(np.float32)
        chunks.append(audio)

        if start % 100 == 0:
            print(f"  chunk {start:3d}-{end:3d}: frames={n_frames} dur={len(audio)/SAMPLE_RATE:.2f}s")

    audio = np.concatenate(chunks)

    # 采样率转换到44100Hz
    if abs(SAMPLE_RATE - ACCEPTABLE_SR) > 1000:
        target_len = int(len(audio) * ACCEPTABLE_SR / SAMPLE_RATE)
        audio = sps.resample(audio, target_len).astype(np.float32)

    # 淡入淡出
    fi = min(int(0.05 * ACCEPTABLE_SR), len(audio) // 4)
    if fi > 0:
        audio[:fi] *= np.linspace(0, 1, fi)
    fo = min(int(0.1 * ACCEPTABLE_SR), len(audio) // 4)
    if fo > 0:
        audio[-fo:] *= np.linspace(1, 0, fo)

    return audio


# ── 主入口 ─────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="YunYe DiffSinger CE 26.07.16")
    ap.add_argument('--project', required=True)
    ap.add_argument('--track', default='02_主唱')
    ap.add_argument('--lyrics-json', default=None)
    args = ap.parse_args()

    proj = os.path.join('workspace', 'project', args.project)
    singer_dir = os.path.join(proj, 'song_engineer', 'track', 'singer')
    os.makedirs(singer_dir, exist_ok=True)

    # 歌词
    ljson_path = args.lyrics_json or os.path.join(proj, 'song_engineer', 'track', '03_lyrics.json')
    if not os.path.exists(ljson_path):
        print(f"[错误] 未找到歌词: {ljson_path}")
        return
    with open(ljson_path, encoding='utf-8') as f:
        ldata = json.load(f)

    # MIDI
    mid_path = os.path.join(proj, 'song_engineer', 'track', f'{args.track}.mid')
    if not os.path.exists(mid_path):
        print(f"[错误] 未找到MIDI: {mid_path}")
        return
    mid = mido.MidiFile(mid_path)
    TPB = mid.ticks_per_beat
    at = 0
    open_n = {}
    midi_notes = []
    for msg in (mid.tracks[1] if len(mid.tracks) > 1 else mid.tracks[0]):
        at += msg.time
        if msg.type == 'note_on' and msg.velocity > 0:
            open_n[msg.note] = (at, msg.velocity)
        elif (msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0) and msg.note in open_n:
            s, v = open_n.pop(msg.note)
            midi_notes.append({'tick': s, 'note': msg.note, 'dur': at - s, 'vel': v})
    midi_notes.sort(key=lambda x: x['tick'])
    midi_notes = midi_notes[:500]  # 限制长度

    # 歌词匹配
    sections = ldata.get('lyric_sections', [])
    lyrics = ['R'] * len(midi_notes)
    idx = 0
    for sec in sections:
        for line in sec.get('lines', []):
            chars = [c for c in line if '一' <= c <= '鿿']
            for ch in chars:
                while idx < len(lyrics) and lyrics[idx] == 'R':
                    lyrics[idx] = ch
                    idx += 1
                    if idx >= len(lyrics):
                        return
                if idx >= len(lyrics):
                    break
            if idx >= len(lyrics):
                break
        if idx >= len(lyrics):
            break

    filled = sum(1 for l in lyrics if l != 'R')
    print(f"音符: {len(midi_notes)}, 已填词: {filled}/{len(lyrics)}")

    print("推理合成...")
    audio = synthesize(midi_notes, lyrics, bpm=68)
    dur = len(audio) / ACCEPTABLE_SR
    peak = float(np.max(np.abs(audio)))
    print(f"输出: {dur:.1f}s, 峰值: {peak:.3f}")

    # 保存
    out_wav = os.path.join(singer_dir, f'{args.track}.wav')
    tmp = os.path.join(tempfile.gettempdir(), '__yunye__.wav')
    try:
        sf.write(tmp, audio, ACCEPTABLE_SR, subtype='PCM_16')
        if os.path.exists(out_wav):
            os.remove(out_wav)
        shutil.copy(tmp, out_wav)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    # 归一化
    if peak > 0.891:
        d, sr = sf.read(out_wav)
        d = d * (0.891 / peak)
        sf.write(out_wav, d, sr, subtype='PCM_16')
        print(f"归一化: {peak:.3f} → 0.891")

    print(f"✓ 已保存: {out_wav}")


if __name__ == '__main__':
    main()
