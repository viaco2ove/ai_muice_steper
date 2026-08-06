# -*- coding: utf-8 -*-
"""YunYe DiffSinger CE 完整7步pipeline合成

Pipeline:
  1. duration_linguistic : tokens+langs+word_div+word_dur -> encoder_out, x_masks   (主 phonemes.json 219)
  2. dur                : encoder_out+x_masks+ph_midi+spk -> ph_dur_pred (ticks)
  3. pitch_linguistic   : tokens+langs+ph_dur(frames) -> encoder_out                   (dspitch/phonemes.json 74)
  4. pitch              : encoder_out+ph_dur+note_midi/note_dur(frames)+pitch+expr+retake+spk+steps -> pitch_pred (midi值)
  5. variance           : dur_encoder_out+ph_dur(frames)+pitch(Hz)+breath/voicing/tension+retake(3)+spk+steps -> breath/voicing/tension_pred
  6. acoustic           : tokens+langs+durations(frames)+f0(Hz)+breath+voicing+tension+gender+velocity+spk+depth+steps -> mel(128bin)
  7. vocoder            : mel+f0(Hz) -> waveform

关键单位:
  - duration: ph_dur_pred 输出 ticks; linguistic word_dur 输入 ticks
  - pitch/variance/acoustic: ph_dur 输入 frames (1帧 = 1/86.1s); note_dur frames
  - pitch_pred 输出 midi 值, 需转 Hz 喂给 acoustic/vocoder
  - fps = 44100/512 = 86.13
"""
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
LING_DUR = os.path.join(VB, "variance_assets", "duration_assets", "linguistic.onnx")
DUR_PATH = os.path.join(VB, "variance_assets", "duration_assets", "dur.onnx")
VAR_PATH = os.path.join(VB, "variance_assets", "duration_assets", "variance.onnx")
LING_PITCH = os.path.join(VB, "dspitch", "linguistic.onnx")
PITCH_PATH = os.path.join(VB, "dspitch", "pitch.onnx")
PH_JSON = os.path.join(VB, "phonemes.json")           # 219 (duration/acoustic/variance)
LANG_JSON = os.path.join(VB, "languages.json")
PH_JSON_P = os.path.join(VB, "dspitch", "phonemes.json")  # 74 (pitch)
LANG_JSON_P = os.path.join(VB, "dspitch", "languages.json")
DICT_ZH = os.path.join(VB, "dsdur", "dsdict-zh.yaml")
EMB_PATH = os.path.join(VB, "yunye.emb")

SR_WRITE = 44100
SR_VOC = 44109
FPS = 86.13  # 44100/512

# 全局资源
_res = None


def load_res():
    global _res
    if _res is not None:
        return
    print("  loading resources...")
    with open(PH_JSON, encoding="utf-8") as f:
        ph = json.load(f)
    with open(PH_JSON_P, encoding="utf-8") as f:
        ph_p = json.load(f)
    with open(LANG_JSON, encoding="utf-8") as f:
        lang = json.load(f)
    with open(LANG_JSON_P, encoding="utf-8") as f:
        lang_p = json.load(f)
    with open(DICT_ZH, encoding="utf-8") as f:
        d = yaml.safe_load(f)

    zh = lang["zh"]
    zh_p = lang_p["zh"]
    # clamp: acoustic/duration embedding 表行数 = max_id (ID 0..max_id-1),
    # 但 phonemes.json 把 zh/zh 映射到 max_id(越界), 需 clamp 到 max_id-1
    max_d_id = max(ph.values())  # 206, embedding 行数 206 -> ID 0-205
    for k, v in ph.items():
        if v >= max_d_id:
            ph[k] = max_d_id - 1  # 205
    max_p_id = max(ph_p.values())
    for k, v in ph_p.items():
        if v >= max_p_id:
            ph_p[k] = max_p_id - 1

    # pinyin -> [(dur_id, pitch_id)] 两个音素表都查
    py2ids = {}
    for e in d.get("entries", []):
        py = e.get("grapheme", "")
        phs = e.get("phonemes", [])
        if isinstance(phs, str):
            phs = [phs]
        ids = []
        ok = True
        for p in phs:
            did = ph.get(p)
            pid = ph_p.get(p)
            if did is None:
                ok = False
                break
            ids.append((did, pid))
        if py and ok and ids:
            py2ids[py] = ids

    spk = np.fromfile(EMB_PATH, dtype=np.float32).astype(np.float32)
    opts = ort.SessionOptions()
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

    _res = {
        "ph": ph, "ph_p": ph_p, "lang": lang, "lang_p": lang_p,
        "zh": zh, "zh_p": zh_p, "py2ids": py2ids, "spk": spk, "opts": opts,
    }
    print("  ph_dur=%d ph_pitch=%d py2ids=%d" % (len(ph), len(ph_p), len(py2ids)))


def lyric_ids(ch):
    load_res()
    r = _res
    sp_id_d = r["ph"].get("SP", 4)
    sp_id_p = r["ph_p"].get("SP", 4)
    if ch in ("R", "sp", "sil", "", "-", "X", "…", "ҭ"):
        return [(sp_id_d, sp_id_p, r["zh"], r["zh_p"])]
    if not HAS_PYPINYIN:
        return [(sp_id_d, sp_id_p, r["zh"], r["zh_p"])]
    try:
        result = pinyin(ch, style=Style.NORMAL)
        p = result[0][0] if result and result[0] else None
    except Exception:
        p = None
    if not p:
        return [(sp_id_d, sp_id_p, r["zh"], r["zh_p"])]
    if p in r["py2ids"]:
        return [(d, p_, r["zh"], r["zh_p"]) for (d, p_) in r["py2ids"][p]]
    return [(sp_id_d, sp_id_p, r["zh"], r["zh_p"])]


def midi_hz(m):
    m = np.asarray(m, dtype=np.float64)
    result = 440.0 * (2.0 ** ((m - 69) / 12.0))
    result = np.where(m <= 0, 0.0, result)
    return result


def synth(notes, lyrics, bpm=68.0, chunk_notes=4):
    """完整7步pipeline, 按音符分块"""
    load_res()
    r = _res
    TPB = 480
    tps = TPB * bpm / 60.0

    # 加载所有模型
    opts = r["opts"]
    prov = ["CPUExecutionProvider"]
    print("  loading models...")
    sess = {
        "ling_dur": ort.InferenceSession(LING_DUR, opts, providers=prov),
        "dur": ort.InferenceSession(DUR_PATH, opts, providers=prov),
        "var": ort.InferenceSession(VAR_PATH, opts, providers=prov),
        "ling_p": ort.InferenceSession(LING_PITCH, opts, providers=prov),
        "pitch": ort.InferenceSession(PITCH_PATH, opts, providers=prov),
        "ac": ort.InferenceSession(AC_PATH, opts, providers=prov),
        "voc": ort.InferenceSession(VOC_PATH, opts, providers=prov),
    }
    print("  models loaded (7)")

    chunks = []
    N = len(notes)
    for start in range(0, N, chunk_notes):
        end = min(start + chunk_notes, N)
        wav = None
        try:
            wav = synth_chunk(notes[start:end], lyrics[start:end], sess, r, tps, bpm)
            chunks.append(wav)
        except Exception as ex:
            print("  chunk %d-%d FAILED: %s" % (start, end, ex))
            dur_est = sum(notes[i]["dur"] for i in range(start, end)) / tps
            chunks.append(np.zeros(int(dur_est * SR_VOC), dtype=np.float32))
        if start % 40 == 0 and wav is not None:
            print("  chunk %d-%d OK (%.2fs)" % (start, end, len(wav) / SR_VOC))

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


def synth_chunk(notes, lyrics, sess, r, tps, bpm):
    """单块7步推理 (R休止符作为SP token参与, f0=0)"""
    tok_d, tok_p, lng_d, lng_p, midi_vals = [], [], [], [], []
    word_div, word_dur = [], []
    note_seq = []  # 全部音符(含R)
    note_is_rest = []

    for nn, ly in zip(notes, lyrics):
        seq = lyric_ids(ly)
        is_rest = (ly == "R")
        word_div.append(len(seq))
        word_dur.append(int(nn["dur"]))
        note_seq.append(nn)
        note_is_rest.append(is_rest)
        for did, pid, ldid, lpid in seq:
            tok_d.append(did)
            tok_p.append(pid)
            lng_d.append(ldid)
            lng_p.append(lpid)
            # R休止符用midi=0 (rest), 否则用真实音高
            midi_vals.append(0 if is_rest else nn["note"])

    if not tok_d:
        dur_est = sum(nn["dur"] for nn in notes) / tps
        return np.zeros(int(dur_est * SR_VOC), dtype=np.float32)

    n_tok = len(tok_d)
    n_note = len(note_seq)
    tok_d = np.array([tok_d], dtype=np.int64)
    tok_p = np.array([tok_p], dtype=np.int64)
    lng_d = np.array([lng_d], dtype=np.int64)
    lng_p = np.array([lng_p], dtype=np.int64)
    word_div = np.array([word_div], dtype=np.int64)
    word_dur = np.array([word_dur], dtype=np.int64)
    midi_vals_arr = np.array([midi_vals], dtype=np.int64)

    spk = r["spk"]

    # ── Step1: duration_linguistic ──
    enc_d, mask_d = sess["ling_dur"].run(None, {
        "tokens": tok_d, "languages": lng_d,
        "word_div": word_div, "word_dur": word_dur,
    })

    # ── Step2: dur_pred -> ph_dur (ticks) ──
    ph_midi = midi_vals_arr  # (1, n_tok)
    spk_tok = np.broadcast_to(spk[np.newaxis, np.newaxis, :], (1, n_tok, 384)).astype(np.float32)
    ph_dur_ticks = sess["dur"].run(None, {
        "encoder_out": enc_d, "x_masks": mask_d,
        "ph_midi": ph_midi, "spk_embed": spk_tok,
    })[0]  # (1, n_tok)

    # ph_dur -> frames (用预测ticks转秒再转帧), 保底每token至少3帧
    ph_dur_sec = ph_dur_ticks[0] / tps
    ph_dur_frames = np.maximum(3, np.round(ph_dur_sec * FPS).astype(np.int64))
    total_frames = int(ph_dur_frames.sum())
    n_frames = max(10, total_frames)

    # ── Step3: pitch_linguistic ──
    enc_p, mask_p = sess["ling_p"].run(None, {
        "tokens": tok_p, "languages": lng_p,
        "ph_dur": ph_dur_frames.reshape(1, -1),
    })

    # ── Step4: pitch_pred -> midi值 ──
    note_midi = np.array([[float(0 if rest else nn["note"]) for nn, rest in zip(note_seq, note_is_rest)]], dtype=np.float32)
    note_rest = np.array([note_is_rest], dtype=bool)
    note_dur_frames = []
    idx = 0
    for nn, wd in zip(note_seq, word_div[0]):
        nf = int(ph_dur_frames[idx:idx + wd].sum())
        note_dur_frames.append(nf)
        idx += wd
    note_dur = np.array([note_dur_frames], dtype=np.int64)

    pitch_in = np.zeros((1, n_frames), dtype=np.float32)
    expr = np.zeros((1, n_frames), dtype=np.float32)
    retake_p = np.ones((1, n_frames), dtype=bool)
    spk_fr = np.broadcast_to(spk[np.newaxis, np.newaxis, :], (1, n_frames, 384)).astype(np.float32)
    pitch_pred_midi = sess["pitch"].run(None, {
        "encoder_out": enc_p, "ph_dur": ph_dur_frames.reshape(1, -1),
        "note_midi": note_midi, "note_rest": note_rest, "note_dur": note_dur,
        "pitch": pitch_in, "expr": expr, "retake": retake_p, "spk_embed": spk_fr,
        "steps": np.array(30, dtype=np.int64),
    })[0]

    # midi -> Hz (休止帧f0=0)
    f0 = midi_hz(pitch_pred_midi).astype(np.float32)
    # 对note_rest对应的帧强制f0=0
    cum = 0
    for rest, nf in zip(note_is_rest, note_dur_frames):
        if rest:
            f0[0, cum:cum + nf] = 0.0
        cum += nf

    # ── Step5: variance -> breath/voicing/tension ──
    retake_v = np.ones((1, n_frames, 3), dtype=bool)
    var_out = sess["var"].run(None, {
        "encoder_out": enc_d, "ph_dur": ph_dur_frames.reshape(1, -1),
        "pitch": f0,
        "breathiness": np.zeros((1, n_frames), dtype=np.float32),
        "voicing": np.ones((1, n_frames), dtype=np.float32),
        "tension": np.zeros((1, n_frames), dtype=np.float32),
        "retake": retake_v, "spk_embed": spk_fr,
        "steps": np.array(20, dtype=np.int64),
    })
    breath, voicing, tension = var_out[0], var_out[1], var_out[2]
    # 休止帧 voicing=0 (无声)
    cum = 0
    for rest, nf in zip(note_is_rest, note_dur_frames):
        if rest:
            voicing[0, cum:cum + nf] = 0.0
        cum += nf

    # ── Step6: acoustic -> mel ──
    mel = sess["ac"].run(None, {
        "tokens": tok_d, "languages": lng_d,
        "durations": ph_dur_frames.reshape(1, -1),
        "f0": f0, "breathiness": breath, "voicing": voicing, "tension": tension,
        "gender": np.zeros((1, n_frames), dtype=np.float32),
        "velocity": np.ones((1, n_frames), dtype=np.float32),
        "spk_embed": spk_fr,
        "depth": np.array(1.0, dtype=np.float32),
        "steps": np.array(30, dtype=np.int64),
    })[0]

    # ── Step7: vocoder ──
    wav = sess["voc"].run(None, {
        "mel": mel.astype(np.float32), "f0": f0.astype(np.float32),
    })[0]
    return wav.flatten().astype(np.float32)


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
    TPB = mid.ticks_per_beat
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

    # 歌词按小节匹配
    bar_segs = [
        (5, 12, 1), (13, 20, 2), (21, 24, 3), (25, 32, 4),
        (33, 40, 5), (41, 47, 6), (48, 52, 7),
    ]
    sections = ldata.get("lyric_sections", [])
    lyrics = ["R"] * len(midi_n)
    for b1, b2, sec_idx in bar_segs:
        if sec_idx >= len(sections):
            continue
        seg_chars = []
        for line in sections[sec_idx].get("lines", []):
            for ch in line:
                if "一" <= ch <= "鿿":
                    seg_chars.append(ch)
        if not seg_chars:
            continue
        idxs = [i for i, n in enumerate(midi_n) if b1 <= n["tick"] // (TPB * 4) + 1 <= b2]
        if not idxs:
            continue
        threshold = 360
        while threshold >= 60:
            cands = [i for i in idxs if midi_n[i]["dur"] >= threshold]
            if len(cands) >= len(seg_chars):
                break
            threshold -= 60
        if len(cands) < len(seg_chars):
            cands = sorted(idxs, key=lambda i: -midi_n[i]["dur"])[:len(seg_chars)]
            cands.sort(key=lambda i: midi_n[i]["tick"])
        for i, ch in zip(cands[:len(seg_chars)], seg_chars):
            lyrics[i] = ch

    filled = sum(1 for l in lyrics if l != "R")
    print("notes=%d filled=%d" % (len(midi_n), filled))
    print("synthesizing (7-step pipeline)...")
    audio = synth(midi_n, lyrics, bpm=args.bpm)
    dur = len(audio) / SR_WRITE
    peak = float(np.max(np.abs(audio)))
    print("output: %.1fs peak=%.3f" % (dur, peak))

    out = os.path.join(singer, args.track + ".wav")
    tmp = os.path.join(tempfile.gettempdir(), "__yunye7__.wav")
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