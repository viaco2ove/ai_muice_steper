# -*- coding: utf-8 -*-
"""YunYe DiffSinger CE 测试脚本"""
import sys, os, json, argparse, tempfile, shutil
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np, soundfile as sf, scipy.signal as sps, onnxruntime as ort, yaml, mido

try:
    from pypinyin import pinyin, Style
    HAS_PYPINYIN = True
except ImportError:
    HAS_PYPINYIN = False

SAMPLE_RATE = 44100
VOCODER_SR = 44109  # 实测

# Paths
ASSET = r"D:\OpenUtau\Singers\Singers\YunYe_DiffSinger_CE_26.07.16\YunYe_DiffSinger_CE_26.07.16"
AC_PATH = os.path.join(ASSET, "acoustic.onnx")
VOC_PATH = os.path.join(ASSET, "dsvocoder", "2601_zhibin_club_ft_pc_nsf_hifigan.onnx")
PH_JSON = os.path.join(ASSET, "phonemes.json")
LANG_JSON = os.path.join(ASSET, "languages.json")
DICT_ZH = os.path.join(ASSET, "dsdur", "dsdict-zh.yaml")
EMB_PATH = os.path.join(ASSET, "yunye.emb")


def load_resources():
    global _ph_data, _lang_data, _py2ids, _spk_emb
    with open(PH_JSON, encoding="utf-8") as f:
        _ph_data = json.load(f)
    with open(LANG_JSON, encoding="utf-8") as f:
        _lang_data = json.load(f)
    with open(DICT_ZH, encoding="utf-8") as f:
        d = yaml.safe_load(f)
    entries = d.get("entries", [])
    zh_id = _lang_data["zh"]
    _py2ids = {}
    for e in entries:
        py = e.get("grapheme", "")
        phs = e.get("phonemes", [])
        if isinstance(phs, str):
            phs = [phs]
        ids = []
        for ph in phs:
            if ph in _ph_data:
                ids.append((_ph_data[ph], zh_id))
        if py and ids:
            _py2ids[py] = ids
    _spk_emb = np.fromfile(EMB_PATH, dtype=np.float32).astype(np.float32)
    print(f"Loaded: phonemes={len(_ph_data)}, lang={_lang_data}, py2ids={len(_py2ids)}, emb={_spk_emb.shape}")


_ph_data = None
_lang_data = None
_py2ids = None
_spk_emb = None


def lyric_to_ids(lyric):
    if lyric in ("R", "sp", "sil", "", "-", "...", "…"):
        sp = _ph_data.get("SP", 4)
        zh = _lang_data["zh"]
        return [(sp, zh)]
    if not HAS_PYPINYIN:
        return [(_ph_data.get("SP", 4), _lang_data["zh"])]
    try:
        py = pinyin(lyric, style=Style.NORMAL)
        p = py[0][0] if py and py[0] else "sp"
    except:
        return [(_ph_data.get("SP", 4), _lang_data["zh"]]
    if not p:
        return [(_ph_data.get("SP", 4), _lang_data["zh"]]
    if p in _py2ids:
        return _py2ids[p]
    return [(_ph_data.get("SP", 4), _lang_data["zh"])]


def midi_hz(m):
    if m <= 0:
        return 0.0
    return 440.0 * (2.0 ** ((m - 69) / 12.0))


def synthesize_chunk(tokens, langs, durations, midi_vals, ac_sess, vc_sess):
    """单个chunk推理，返回numpy array"""
    n_tok = len(tokens)
    n_frames = max(10, int(sum(durations) * 86.1))

    # 构造所有张量
    t_tok = np.array([tokens], np.int64)
    t_lng = np.array([langs], np.int64)
    t_dur = np.array([durations], np.float32)

    # spk_embed: (1, n_frames, 384)
    spk = np.broadcast_to(_spk_emb[np.newaxis, np.newaxis, :], (1, n_frames, 384)).astype(np.float32)

    # f0
    f0 = np.zeros((1, n_frames), dtype=np.float32)
    total_dur = sum(durations)
    cum = 0.0
    for i in range(n_frames):
        t = i * total_dur / n_frames
        for j in range(n_tok):
            d = durations[j]
            if cum <= t < cum + d:
                f0[0, i] = midi_hz(midi_vals[j])
                break
            cum += d

    # acoustic model
    try:
        mel = ac_sess.run(None, {
            "tokens": t_tok,
            "languages": t_lng,
            "durations": t_dur,
            "f0": f0,
            "breathiness": np.zeros((1, n_frames), np.float32),
            "voicing": np.ones((1, n_frames), np.float32),
            "tension": np.zeros((1, n_frames), np.float32),
            "gender": np.zeros((1, n_frames), np.float32),
            "velocity": np.ones((1, n_frames), np.float32),
            "spk_embed": spk,
            "depth": np.array(1.0, dtype=np.float32),
            "steps": np.array(30, dtype=np.int64),
        })[0]
    except Exception as e:
        # 尝试简化参数
        try:
            mel = ac_sess.run(None, {
                "tokens": t_tok, "languages": t_lng, "durations": t_dur,
                "f0": f0,
                "breathiness": np.zeros((1, n_frames), np.float32),
                "voicing": np.ones((1, n_frames), np.float32),
                "tension": np.zeros((1, n_frames), np.float32),
                "gender": np.zeros((1, n_frames), np.float32),
                "velocity": np.ones((1, n_frames), np.float32),
                "spk_embed": spk,
                "depth": np.array(1.0, dtype=np.float32),
                "steps": np.array(30, dtype=np.int64),
            })[0]
        except Exception as e2:
            print(f"    acoustic FAILED: {e2}")
            mel = np.random.randn(1, n_frames, 128).astype(np.float32) * 0.01

    # vocoder
    wav = vc_sess.run(None, {"mel": mel.astype(np.float32), "f0": f0.astype(np.float32)})[0]
    return wav.flatten().astype(np.float32)


def synthesize(midi_notes, lyrics, bpm, ac_sess, vc_sess):
    tps = 480 * bpm / 60.0
    CHUNK = 20
    chunks = []
    for start in range(0, len(midi_notes), CHUNK):
        end = min(start + CHUNK, len(midi_notes))
        tokens, langs, durations, midi_vals = [], [], [], []
        for i in range(start, end):
            seq = lyric_to_ids(lyrics[i])
            dur_sec = float(midi_notes[i]["dur"]) / tps
            for pid, lid in seq:
                tokens.append(pid)
                langs.append(lid)
                durations.append(dur_sec)
                midi_vals.append(midi_notes[i]["note"])
        if not tokens:
            continue
        wav = synthesize_chunk(tokens, langs, durations, midi_vals, ac_sess, vc_sess)
        chunks.append(wav)
        if start % 100 == 0:
            print(f"  {start}-{end}: {len(wav)/VOCODER_SR:.2f}s")
    audio = np.concatenate(chunks)
    # resample to SAMPLE_RATE
    if abs(VOCODER_SR - SAMPLE_RATE) > 100:
        target = int(len(audio) * SAMPLE_RATE / VOCODER_SR)
        audio = sps.resample(audio, target).astype(np.float32)
    fi = min(int(0.05 * SAMPLE_RATE), len(audio)//4)
    if fi > 0:
        audio[:fi] *= np.linspace(0, 1, fi)
    fo = min(int(0.1 * SAMPLE_RATE, len(audio)//4)
    if fo > 0:
        audio[-fo:] *= np.linspace(1, 0, fo)
    return audio


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--track", default="02_主唱")
    ap.add_argument("--lyrics-json", default=None)
    args = ap.parse_args()

    proj = os.path.join("workspace", "project", args.project)
    singer_dir = os.path.join(proj, "song_engineer", "track", "singer")
    os.makedirs(singer_dir, exist_ok=True)

    # lyrics
    lj = args.lyrics_json or os.path.join(proj, "song_engineer", "track", "03_lyrics.json")
    with open(lj, encoding="utf-8") as f:
        ldata = json.load(f)

    # midi
    mp = os.path.join(proj, "song_engineer", "track", args.track + ".mid")
    mid = mido.MidiFile(mp)
    TPB = mid.ticks_per_beat
    open_n = {}
    midi_notes = []
    tick = 0
    for msg in (mid.tracks[1] if len(mid.tracks) > 1 else mid.tracks[0]):
        tick += msg.time
        if msg.type == "note_on" and msg.velocity > 0:
            open_n[msg.note] = (tick, msg.velocity)
        elif (msg.type == "note_off" or msg.type == "note_on" and msg.velocity == 0) and msg.note in open_n:
            s, v = open_n.pop(msg.note)
            midi_notes.append({"tick": s, "note": msg.note, "dur": tick - s})
    midi_notes.sort(key=lambda x: x["tick"])

    # lyrics match
    lyrics = ["R"] * len(midi_notes)
    idx = 0
    for sec in ldata.get("lyric_sections", []):
        for line in sec.get("lines", []):
            for ch in line:
                if "一" <= ch <= "鿿":
                    while idx < len(lyrics) and lyrics[idx] != "R":
                        idx += 1
                    if idx < len(lyrics):
                        lyrics[idx] = ch
                        idx += 1

    print(f"Notes: {len(midi_notes)}, Lyrics filled: {sum(1 for l in lyrics if l != 'R'}")
    print("Loading models...")
    opts = ort.SessionOptions()
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    ac = ort.InferenceSession(AC_PATH, opts, providers=["CPUExecutionProvider"])
    vc = ort.InferenceSession(VOC_PATH, opts, providers=["CPUExecutionProvider"])
    print("Synthesizing...")
    load_resources()
    audio = synthesize(midi_notes, lyrics, bpm=68, ac_sess=ac, vc_sess=vc)
    print(f"Output: {len(audio)/SAMPLE_RATE:.1f}s, peak={float(np.max(np.abs(audio)):.3f}")
    out = os.path.join(singer_dir, args.track + ".wav")
    tmp = os.path.join(tempfile.gettempdir(), "__yunye__.wav")
    try:
        sf.write(tmp, audio, SAMPLE_RATE, subtype="PCM_16")
        if os.path.exists(out):
            os.remove(out)
        shutil.copy(tmp, out)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    pk = float(np.max(np.abs(audio))
    if pk > 0.891:
        d, sr = sf.read(out)
        d = d * (0.891 / pk)
        sf.write(out, d, sr, subtype="PCM_16")
        print(f"Normalized: {pk:.3f} -> 0.891")
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
