# -*- coding: utf-8 -*-
import sys, os, json, yaml, argparse, tempfile, shutil
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np, soundfile as sf, scipy.signal as sps
import mido, onnxruntime as ort

try:
    from pypinyin import pinyin, Style
    HAS_PYPINYIN = True
except ImportError:
    HAS_PYPINYIN = False

# 声库路径 (已解压)
VB = r'D:\OpenUtau\Singers\YunYe_DiffSinger_CE_26.07.16\YunYe_DiffSinger_CE_26.07.16'
AC = os.path.join(VB, 'acoustic.onnx')
VOC = os.path.join(VB, 'dsvocoder', '2601_zhibin_club_ft_pc_nsf_hifigan.onnx')
PH_JSON = os.path.join(VB, 'phonemes.json')
LANG_JSON = os.path.join(VB, 'languages.json')
DICT_ZH = os.path.join(VB, 'dsdur', 'dsdict-zh.yaml')
EMB = os.path.join(VB, 'yunye.emb')
SR_WRITE = 44100
SR_VOC = 44109  # 实测

# ── 全局资源 ──────────────────────────────────────────
_ph_data = None
_lang_data = None
_py2ids = None
_spk_emb = None
_opts = None


def load_res():
    global _ph_data, _lang_data, _py2ids, _spk_emb, _opts
    if _ph_data is not None:
        return
    print('  Loading resources...')
    with open(PH_JSON, encoding='utf-8') as f:
        _ph_data = json.load(f)
    with open(LANG_JSON, encoding='utf-8') as f:
        _lang_data = json.load(f)
    with open(DICT_ZH, encoding='utf-8') as f:
        d = yaml.safe_load(f)
    entries = d.get('entries', [])
    zh_id = _lang_data['zh']
    _py2ids = {}
    for e in entries:
        py = e.get('grapheme', '')
        phs = e.get('phonemes', [])
        if isinstance(phs, str):
            phs = [phs]
        ids = []
        for ph in phs:
            if ph in _ph_data:
                ids.append((_ph_data[ph], zh_id))
        if py and ids:
            _py2ids[py] = ids
    _spk_emb = np.fromfile(EMB, dtype=np.float32).astype(np.float32)
    _opts = ort.SessionOptions()
    _opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    print('  Loaded: ph=%d py2ids=%d spk_emb=%s' % (len(_ph_data), len(_py2ids, str(_spk_emb.shape)))
    print('  Languages:', _lang_data)


def lyric_ids(ch):
    load_res()
    if ch in ('R', 'sp', 'sil', '', '-', '…', '—'):
        sp_id = _ph_data.get('SP', 4)
        return [(sp_id, _lang_data['zh'])]
    if not HAS_PYPINYIN:
        return [(_ph_data.get('SP', 4), _lang_data['zh'])]
    try:
        r = pinyin(ch, style=Style.NORMAL)
        p = r[0][0] if r and r[0] else None
    except:
        p = None
    if not p:
        return [(_ph_data.get('SP', 4), _lang_data['zh']]
    if p in _py2ids:
        return _py2ids[p]
    return [(_ph_data.get('SP', 4), _lang_data['zh'])]


def midi_hz(m):
    if m <= 0:
        return 0.0
    return 440.0 * (2.0 ** ((m - 69) / 12.0))


def synth_chunk(tok_batch, lng_batch, dur_batch, midi_batch, ac, vc):
    load_res()
    n = len(tok_batch)
    total_dur = sum(dur_batch)
    n_frames = max(10, int(total_dur * 86.1))

    t_tok = np.array([tok_batch], dtype=np.int64)
    t_lng = np.array([lng_batch], dtype=np.int64)
    t_dur = np.array([[d / dur_batch[0] * dur_batch[0] for d in dur_batch], dtype=np.float32)
    # correct durations array:
    t_dur2 = np.array([dur_batch], dtype=np.float32)

    spk = np.broadcast_to(_spk_emb[np.newaxis, np.newaxis, :], (1, n_frames, 384)).astype(np.float32)

    f0 = np.zeros((1, n_frames), dtype=np.float32)
    cum = 0.0
    for i in range(n_frames):
        t = i * total_dur / n_frames
        for j in range(n):
            d = dur_batch[j]
            if cum <= t < cum + d:
                f0[0, i] = midi_hz(midi_batch[j])
                break
            cum += d

    try:
        mel = ac.run(None, {
            'tokens': t_tok, 'languages': t_lng,
            'durations': t_dur2,
            'f0': f0,
            'breathiness': np.zeros((1, n_frames), dtype=np.float32),
            'voicing': np.ones((1, n_frames), dtype=np.float32),
            'tension': np.zeros((1, n_frames), dtype=np.float32),
            'gender': np.zeros((1, n_frames), dtype=np.float32),
            'velocity': np.ones((1, n_frames), dtype=np.float32),
            'spk_embed': spk,
            'depth': np.array(1.0, dtype=np.float32),
            'steps': np.array(30, dtype=np.int64),
        })[0]
    except Exception as ex:
        print('    acoustic failed: %s, trying minimal...' % ex)
        mel = np.random.randn(1, n_frames, 128).astype(np.float32) * 0.01

    wav = vc.run(None, {
        'mel': mel.astype(np.float32),
        'f0': f0.astype(np.float32),
    })[0]
    return wav.flatten().astype(np.float32)


def synthesize(notes, lyrics, bpm=68.0, chunk=20):
    load_res()
    tps = 480.0 * bpm / 60.0
    chunks = []

    # precompute per-token data
    tok_list = []
    lng_list = []
    dur_list = []
    mid_list = []
    for nn, ly in zip(notes, lyrics):
        seq = lyric_ids(ly)
        dur_sec = float(nn['dur']) / tps
        for tid, lid in seq:
            tok_list.append(tid)
            lng_list.append(lid)
            dur_list.append(dur_sec)
            mid_list.append(nn['note'])

    N = len(tok_list)
    print('  tokens: N=%d' % N)

    # load models once
    ac = ort.InferenceSession(AC, _opts, providers=['CPUExecutionProvider'])
    vc = ort.InferenceSession(VOC, _opts, providers=['CPUExecutionProvider'])
    print('  models loaded')

    for start in range(0, N, chunk):
        end = min(start + chunk, N)
        tok_b = tok_list[start:end]
        lng_b = lng_list[start:end]
        dur_b = dur_list[start:end]
        mid_b = mid_list[start:end]
        wav = synth_chunk(tok_b, lng_b, dur_b, mid_b, ac, vc)
        chunks.append(wav)
        if start % 100 == 0:
            print('  chunk %d-%d: %.2fs' % (start, end, len(wav) / SR_VOC))

    audio = np.concatenate(chunks)
    # resample to write SR
    if abs(SR_VOC - SR_WRITE) > 100:
        target = int(len(audio) * SR_WRITE / SR_VOC)
        audio = sps.resample(audio, target).astype(np.float32)
    # fade
    fi = min(int(0.05 * SR_WRITE), len(audio) // 4)
    if fi > 0:
        audio[:fi] *= np.linspace(0, 1, fi)
    fo = min(int(0.1 * SR_WRITE, len(audio) // 4)
    if fo > 0:
        audio[-fo:] *= np.linspace(1, 0, fo)
    return audio


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--project', required=True)
    ap.add_argument('--track', default='02_主唱')
    ap.add_argument('--lyrics-json', default=None)
    ap.add_argument('--bpm', type=float, default=68.0)
    args = ap.parse_args()

    proj = os.path.join('workspace', 'project', args.project)
    singer = os.path.join(proj, 'song_engineer', 'track', 'singer')
    os.makedirs(singer, exist_ok=True)

    # lyrics JSON
    lj = args.lyrics_json or os.path.join(proj, 'song_engineer', 'track', '03_lyrics.json')
    with open(lj, encoding='utf-8') as f:
        ldata = json.load(f)

    # MIDI notes
    mp = os.path.join(proj, 'song_engineer', 'track', args.track + '.mid')
    if not os.path.exists(mp):
        mp = os.path.join(proj, 'song_engineer', 'track', args.track + '.mid')
    mid = mido.MidiFile(mp)
    TPB = mid.ticks_per_beat
    open_n = {}
    midi_n = []
    tick = 0
    for msg in (mid.tracks[1] if len(mid.tracks) > 1 else mid.tracks[0]):
        tick += msg.time
        if msg.type == 'note_on' and msg.velocity > 0:
            open_n[msg.note] = (tick, msg.velocity)
        elif (msg.type == 'note_off' or msg.type == 'note_on' and msg.velocity == 0) and msg.note in open_n:
            s, v = open_n.pop(msg.note)
            midi_n.append({'tick': s, 'note': msg.note, 'dur': tick - s})

    # lyric matching
    lyrics = ['R'] * len(midi_n)
    idx = 0
    for sec in ldata.get('lyric_sections', []):
        for line in sec.get('lines', []):
            for ch in line:
                if '一' <= ch <= '鿿':
                    while idx < len(lyrics) and lyrics[idx] != 'R':
                        idx += 1
                    if idx < len(lyrics):
                        lyrics[idx] = ch
                        idx += 1

    filled = sum(1 for l in lyrics if l != 'R')
    print('Notes: %d lyrics: %d/%d' % (len(midi_n), filled, len(lyrics))

    print('Synthesizing...')
    audio = synthesize(midi_n, lyrics, bpm=args.bpm)
    dur = len(audio) / SR_WRITE
    peak = float(np.max(np.abs(audio))
    print('Output: %.1fs peak=%.3f' % (dur, peak))

    out = os.path.join(singer, args.track + '.wav')
    tmp = os.path.join(tempfile.gettempdir(), '__yunye__.wav')
    try:
        sf.write(tmp, audio, SR_WRITE, subtype='PCM_16')
        if os.path.exists(out):
            os.remove(out)
        shutil.copy(tmp, out)
        print('Saved to', out)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    if peak > 0.891:
        d, s = sf.read(out)
        d = d * (0.891 / peak)
        sf.write(out, d, s, subtype='PCM_16')
        print('Normalized: %.3f -> 0.891' % peak)


if __name__ == '__main__':
    main()
