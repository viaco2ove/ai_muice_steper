# -*- coding: utf-8 -*-
import sys, os, json, yaml, argparse, tempfile, shutil
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np, soundfile as sf, scipy.signal as sps
import mido, onnxruntime as ort

try:
    from pypinyin import pinyin, Style
    HAS_PYPINYIN = True
except ImportError:
    HAS_PYPINYIN = False

VB = r"D:\OpenUtau\Singers\YunYe_DiffSinger_CE_26.07.16\YunYe_DiffSinger_CE_26.07.16"
AC_PATH = os.path.join(VB, "acoustic.onnx")
VOC_PATH = os.path.join(VB, "dsvocoder", "2601_zhibin_club_ft_pc_nsf_hifigan.onnx")
PH_JSON = os.path.join(VB, "phonemes.json")
LANG_JSON = os.path.join(VB, "languages.json")
DICT_ZH = os.path.join(VB, "dsdur", "dsdict-zh.yaml")
EMB_PATH = os.path.join(VB, "yunye.emb")

SR_WRITE = 44100
SR_VOC = 44109
MEL_FPS = 86.1

_ph = None
_lang = None
_py2ids = None
_spk = None
_opts = None


def load_res():
    global _ph, _lang, _py2ids, _spk, _opts
    if _ph is not None:
        return
    print("  loading resources...")
    with open(PH_JSON, encoding="utf-8") as f:
        _ph = json.load(f)
    with open(LANG_JSON, encoding="utf-8") as f:
        _lang = json.load(f)
    with open(DICT_ZH, encoding="utf-8") as f:
        d = yaml.safe_load(f)
    zh_id = _lang["zh"]
    _py2ids = {}
    for e in d.get("entries", []):
        py = e.get("grapheme", "")
        phs = e.get("phonemes", [])
        if isinstance(phs, str):
            phs = [phs]
        ids = []
        for p in phs:
            if p in _ph:
                ids.append((_ph[p], zh_id))
        if py and ids:
            _py2ids[py] = ids
    _spk = np.fromfile(EMB_PATH, dtype=np.float32).astype(np.float32)
    _opts = ort.SessionOptions()
    _opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    print("  ph=%d py2ids=%d spk=%s" % (len(_ph), len(_py2ids), str(_spk.shape)))


def lyric_ids(ch):
    load_res()
    if ch in ("R", "sp", "sil", "", "-", "X", "…", "ҭ"):
        return [(_ph.get("SP", 4), _lang["zh"])]
    if not HAS_PYPINYIN:
        return [(_ph.get("SP", 4), _lang["zh"])]
    try:
        r = pinyin(ch, style=Style.NORMAL)
        p = r[0][0] if r and r[0] else None
    except Exception:
        p = None
    if not p:
        return [(_ph.get("SP", 4), _lang["zh"])]
    if p in _py2ids:
        return _py2ids[p]
    return [(_ph.get("SP", 4), _lang["zh"])]


def midi_hz(m):
    if m <= 0:
        return 0.0
    return 440.0 * (2.0 ** ((m - 69) / 12.0))


def synth(notes, lyrics, bpm=68.0, chunk=20):
    load_res()
    tps = 480.0 * bpm / 60.0
    chunks = []

    tok_list = []
    lng_list = []
    dur_frames_list = []
    midi_list = []

    for nn, ly in zip(notes, lyrics):
        seq = lyric_ids(ly)
        dur_sec = float(nn["dur"]) / tps
        n_frames_note = max(2, int(round(dur_sec * MEL_FPS)))
        frames_per_tok = max(1, n_frames_note // max(len(seq), 1))
        for tid, lid in seq:
            tok_list.append(tid)
            lng_list.append(lid)
            dur_frames_list.append(frames_per_tok)
            midi_list.append(nn["note"])

    N = len(tok_list)
    print("  tokens N=%d" % N)
    if N == 0:
        return np.zeros(SR_WRITE, dtype=np.float32)

    ac = ort.InferenceSession(AC_PATH, _opts, providers=["CPUExecutionProvider"])
    vc = ort.InferenceSession(VOC_PATH, _opts, providers=["CPUExecutionProvider"])
    print("  models loaded")

    for start in range(0, N, chunk):
        end = min(start + chunk, N)
        tok_b = tok_list[start:end]
        lng_b = lng_list[start:end]
        dur_b = dur_frames_list[start:end]
        mid_b = midi_list[start:end]
        n_tok = end - start
        n_frames = sum(dur_b)

        t_tok = np.array([tok_b], dtype=np.int64)
        t_lng = np.array([lng_b], dtype=np.int64)
        t_dur = np.array([dur_b], dtype=np.int64)
        spk_e = np.broadcast_to(_spk[np.newaxis, np.newaxis, :], (1, n_frames, 384)).astype(np.float32)

        f0 = np.zeros((1, n_frames), dtype=np.float32)
        cum = 0
        for i in range(n_frames):
            t = i
            for j in range(n_tok):
                d = dur_b[j]
                if cum <= t < cum + d:
                    f0[0, i] = midi_hz(mid_b[j])
                    break
                cum += d

        try:
            mel = ac.run(None, {
                "tokens": t_tok, "languages": t_lng, "durations": t_dur,
                "f0": f0,
                "breathiness": np.zeros((1, n_frames), dtype=np.float32),
                "voicing": np.ones((1, n_frames), dtype=np.float32),
                "tension": np.zeros((1, n_frames), dtype=np.float32),
                "gender": np.zeros((1, n_frames), dtype=np.float32),
                "velocity": np.ones((1, n_frames), dtype=np.float32),
                "spk_embed": spk_e,
                "depth": np.array(1.0, dtype=np.float32),
                "steps": np.array(30, dtype=np.int64),
            })[0]
            wav = vc.run(None, {"mel": mel.astype(np.float32), "f0": f0.astype(np.float32)})[0]
            audio = wav.flatten().astype(np.float32)
            chunks.append(audio)
        except Exception as ex:
            print("  chunk %d-%d FAILED: %s" % (start, end, ex))
            chunks.append(np.zeros(int(n_frames * 512), dtype=np.float32))

        if start % 60 == 0:
            print("  chunk %d-%d: frames=%d dur=%.2fs" % (start, end, n_frames, len(audio)/SR_VOC))

    audio = np.concatenate(chunks)
    if abs(SR_VOC - SR_WRITE) > 100:
        target = int(len(audio) * SR_WRITE / SR_VOC)
        audio = sps.resample(audio, target).astype(np.float32)
    fi = min(int(0.05 * SR_WRITE), len(audio) // 4)
    if fi > 0:
        audio[:fi] *= np.linspace(0, 1, fi)
    fo = min(int(0.1 * SR_WRITE), len(audio) // 4)
    if fo > 0:
        audio[-fo:] *= np.linspace(1, 0, fo)
    return audio


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--track", default="02_主唱")
    ap.add_argument("--lyrics-json", default=None)
    ap.add_argument("--bpm", type=float, default=68.0)
    args = ap.parse_args()

    proj = os.path.join("workspace", "project", args.project)
    singer = os.path.join(proj, "song_engineer", "track", "singer")
    os.makedirs(singer, exist_ok=True)

    lj = args.lyrics_json or os.path.join(proj, "song_engineer", "track", "03_lyrics.json")
    with open(lj, encoding="utf-8") as f:
        ldata = json.load(f)

    mp = os.path.join(proj, "song_engineer", "track", args.track + ".mid")
    mid = mido.MidiFile(mp)
    open_n = {}
    midi_n = []
    tick = 0
    for msg in (mid.tracks[1] if len(mid.tracks) > 1 else mid.tracks[0]):
        tick += msg.time
        if msg.type == "note_on" and msg.velocity > 0:
            open_n[msg.note] = (tick, msg.velocity)
        elif (msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0)) and msg.note in open_n:
            s, v = open_n.pop(msg.note)
            midi_n.append({"tick": s, "note": msg.note, "dur": tick - s})

    lyrics = ["R"] * len(midi_n)
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

    filled = sum(1 for l in lyrics if l != "R")
    print("notes=%d filled=%d" % (len(midi_n), filled))
    print("synthesizing...")
    audio = synth(midi_n, lyrics, bpm=args.bpm)
    dur = len(audio) / SR_WRITE
    peak = float(np.max(np.abs(audio)))
    print("output: %.1fs peak=%.3f" % (dur, peak))

    out = os.path.join(singer, args.track + ".wav")
    tmp = os.path.join(tempfile.gettempdir(), "__yunye__.wav")
    try:
        sf.write(tmp, audio, SR_WRITE, subtype="PCM_16")
        if os.path.exists(out):
            os.remove(out)
        shutil.copy(tmp, out)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

    if peak > 0.891:
        d, s = sf.read(out)
        d = d * (0.891 / peak)
        sf.write(out, d, s, subtype="PCM_16")
        print("normalized: %.3f -> 0.891" % peak)
    print("saved: %s" % out)


if __name__ == "__main__":
    main()
