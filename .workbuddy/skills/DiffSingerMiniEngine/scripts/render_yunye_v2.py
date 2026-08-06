# -*- coding: utf-8 -*-
"""YunYe DiffSinger CE 完整7步pipeline合成 v2

相对 render_yunye_full.py 的修复:
  1. 线性对齐: 1音符=1字符, 按MIDI时间顺序分配; 段内字符用尽后剩余音符用'-'延续(拖腔);
     抛弃 bar_segs 启发式阈值匹配(原方案把R插进句子中间, 音素-音高全面错位)
  2. 时长约束: dur模型预测的ph_dur按word_dur(MIDI实际时值)强制缩放, frames级精确对齐,
     消除原方案24%的节奏漂移(183.5s MIDI -> 139.7s 输出)
  3. 分段推理: R段(休止)直接补零静音, 歌唱段(乐句)整段一次推理, 消除4音符分块的边界断裂;
     开头按首个音符tick补头部静音, 输出与MIDI时间轴严格对齐(方便混音对轨)
  4. '-' 转音符继承前字韵母(原方案错误地按SP静音处理)

Pipeline (与v1相同):
  1. duration_linguistic -> 2. dur -> 3. pitch_linguistic -> 4. pitch
  -> 5. variance -> 6. acoustic -> 7. vocoder
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

# 段落小节范围 -> 03_lyrics.json lyric_sections 索引
# (bar_start, bar_end, section_idx)  bar 从1计
BAR_SEGS = [
    (5, 12, 1),    # Verse 1
    (13, 20, 2),   # Verse 2
    (21, 24, 3),   # Interlude
    (25, 32, 4),   # Chorus 1
    (33, 40, 5),   # Verse 3
    (41, 47, 6),   # Chorus 2
    (48, 52, 7),   # Outro
]

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
    # clamp: embedding 表行数 = max_id, phonemes.json 里 zh/zh 映射到 max_id(越界), clamp 到 max_id-1
    max_d_id = max(ph.values())
    for k, v in ph.items():
        if v >= max_d_id:
            ph[k] = max_d_id - 1
    max_p_id = max(ph_p.values())
    for k, v in ph_p.items():
        if v >= max_p_id:
            ph_p[k] = max_p_id - 1

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
    # 关闭内存池/内存模式缓存: 逐段推理时arena会持续累积不释放, 长曲后段必OOM
    opts.enable_cpu_mem_arena = False
    opts.enable_mem_pattern = False

    _res = {
        "ph": ph, "ph_p": ph_p, "lang": lang, "lang_p": lang_p,
        "zh": zh, "zh_p": zh_p, "py2ids": py2ids, "spk": spk, "opts": opts,
    }
    print("  ph_dur=%d ph_pitch=%d py2ids=%d" % (len(ph), len(ph_p), len(py2ids)))


def lyric_ids(ch):
    """汉字 -> [(dur_id, pitch_id, lang_d, lang_p), ...] (1~2个音素: 声母+韵母)"""
    r = _res
    sp_id_d = r["ph"].get("SP", 4)
    sp_id_p = r["ph_p"].get("SP", 4)
    if ch in ("R", "sp", "sil", "", "X", "…", "ҭ"):
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


# ---------------------------------------------------------------- 线性对齐
def extract_section_chars(lines):
    """从段落 lines 提取有效字符(汉字), 跳过 … 等装饰符"""
    chars = []
    for line in lines:
        for ch in line:
            if "一" <= ch <= "鿿":
                chars.append(ch)
    return chars


def align_lyrics_linear(midi_notes, sections, bar_segs, TPB):
    """1音符=1字符线性对齐; 段内字符用尽后剩余音符用'-'延续韵母(拖腔); 段外 R"""
    lyrics = ["R"] * len(midi_notes)
    for b1, b2, sec_idx in bar_segs:
        if sec_idx >= len(sections):
            continue
        chars = extract_section_chars(sections[sec_idx].get("lines", []))
        if not chars:
            continue
        idxs = [i for i, n in enumerate(midi_notes)
                if b1 <= n["tick"] // (TPB * 4) + 1 <= b2]
        for k, i in enumerate(idxs):
            if k < len(chars):
                lyrics[i] = chars[k]
            else:
                lyrics[i] = "-"
    return lyrics


def split_segments(notes, lyrics, TPB, bar_segs):
    """先按段落小节边界强制切分(防止整段超长导致 vocoder OOM/质量下降),
    段内再按 R/sing 细分。返回 ('rest'|'sing', start, end) 列表"""
    from bisect import bisect_left
    note_ticks = [n["tick"] for n in notes]
    cuts = {0, len(notes)}
    for b1, b2, _ in bar_segs:
        cuts.add(bisect_left(note_ticks, (b1 - 1) * TPB * 4))
        cuts.add(bisect_left(note_ticks, b2 * TPB * 4))
    cuts = sorted(cuts)
    segs = []
    for ca, cb in zip(cuts, cuts[1:]):
        i = ca
        while i < cb:
            j = i
            if lyrics[i] == "R":
                while j < cb and lyrics[j] == "R":
                    j += 1
                segs.append(("rest", i, j))
            else:
                while j < cb and lyrics[j] != "R":
                    j += 1
                segs.append(("sing", i, j))
            i = j
    return segs


# ---------------------------------------------------------------- 合成
def synth(notes, lyrics, sess, bpm=68.0):
    """分段合成: R段补零, 歌唱段整段7步推理; 输出与MIDI时间轴严格对齐"""
    load_res()
    r = _res
    TPB = 480
    tps = TPB * bpm / 60.0

    # 头部静音(首个音符之前的MIDI时间)
    chunks = []
    head_ticks = notes[0]["tick"] if notes else 0
    if head_ticks > 0:
        head_sec = head_ticks / tps
        chunks.append(np.zeros(int(head_sec * SR_VOC), dtype=np.float32))
        print("  head silence: %.2fs" % head_sec)

    segs = split_segments(notes, lyrics, TPB, BAR_SEGS)
    print("  segments: %d (%s)" % (len(segs),
          " ".join("%s:%d-%d" % (k[0], a, b) for k, a, b in segs)))

    for kind, a, b in segs:
        # 段时长用时间跨度(含音符间空隙), 不是时值之和
        seg_ticks = notes[b - 1]["tick"] + notes[b - 1]["dur"] - notes[a]["tick"]
        seg_sec = seg_ticks / tps
        if kind == "rest":
            chunks.append(np.zeros(int(seg_sec * SR_VOC), dtype=np.float32))
            print("  seg %d-%d REST %.1fs -> silence" % (a, b, seg_sec))
            continue
        try:
            sn, sl = expand_gaps(notes[a:b], lyrics[a:b])
            wav = synth_chunk(sn, sl, sess, r, tps, bpm)
            # 严格对齐: 输出长度必须 = MIDI 时值(帧级误差用重采样吸收)
            target = int(seg_sec * SR_VOC)
            if abs(len(wav) - target) > SR_VOC * 0.02:  # 偏差>20ms才修
                wav = sps.resample(wav, target).astype(np.float32)
            chunks.append(wav)
            print("  seg %d-%d SING %.1fs OK (chars=%d)" % (
                a, b, seg_sec, sum(1 for k in range(a, b) if lyrics[k] not in ("R", "-"))))
        except Exception as ex:
            print("  seg %d-%d FAILED: %s" % (a, b, ex))
            chunks.append(np.zeros(int(seg_sec * SR_VOC), dtype=np.float32))
        import gc
        gc.collect()  # 每段后释放推理中间结果

    audio = np.concatenate(chunks)
    if abs(SR_VOC - SR_WRITE) > 100:
        target = int(len(audio) * SR_WRITE / SR_VOC)
        audio = sps.resample(audio, target).astype(np.float32)
    # 首尾淡入淡出
    fi = min(int(0.05 * SR_WRITE), len(audio) // 4)
    if fi > 0:
        audio[:fi] *= np.linspace(0, 1, fi)
    fo = min(int(0.1 * SR_WRITE), len(audio) // 4)
    if fo > 0:
        audio[-fo:] *= np.linspace(1, 0, fo)
    return audio


def expand_gaps(notes, lyrics):
    """段内音符之间插入间隙R音符(SP静音), 使序列在时间轴上连续。
    否则附点节奏/呼吸空隙被吃掉, 全曲节奏漂移(v1/v2首跑的-22%根因)"""
    out_n, out_l = [], []
    for i, (n, l) in enumerate(zip(notes, lyrics)):
        out_n.append(n)
        out_l.append(l)
        if i + 1 < len(notes):
            gap = notes[i + 1]["tick"] - (n["tick"] + n["dur"])
            if gap > 0:
                out_n.append({"tick": n["tick"] + n["dur"], "note": 0, "dur": gap})
                out_l.append("R")
    return out_n, out_l


def synth_chunk(notes, lyrics, sess, r, tps, bpm):
    """整段7步推理; '-'继承前字韵母; ph_dur按MIDI时值强制对齐"""
    tok_d, tok_p, lng_d, lng_p, midi_vals = [], [], [], [], []
    word_div, word_dur = [], []
    note_seq = []
    note_is_rest = []

    last_seq = None  # 前字音素序列, 供'-'继承韵母
    for nn, ly in zip(notes, lyrics):
        is_rest = (ly == "R")
        if ly == "-" and last_seq:
            seq = [last_seq[-1]]  # 只延续韵母
        else:
            seq = lyric_ids(ly)
            if ly != "-":
                last_seq = seq
        word_div.append(len(seq))
        word_dur.append(int(nn["dur"]))
        note_seq.append(nn)
        note_is_rest.append(is_rest)
        for did, pid, ldid, lpid in seq:
            tok_d.append(did)
            tok_p.append(pid)
            lng_d.append(ldid)
            lng_p.append(lpid)
            midi_vals.append(0 if is_rest else nn["note"])

    if not tok_d:
        dur_est = sum(nn["dur"] for nn in notes) / tps
        return np.zeros(int(dur_est * SR_VOC), dtype=np.float32)

    n_tok = len(tok_d)
    n_frames_tok = None
    tok_d = np.array([tok_d], dtype=np.int64)
    tok_p = np.array([tok_p], dtype=np.int64)
    lng_d = np.array([lng_d], dtype=np.int64)
    lng_p = np.array([lng_p], dtype=np.int64)
    word_div_arr = np.array([word_div], dtype=np.int64)
    word_dur_arr = np.array([word_dur], dtype=np.int64)
    midi_vals_arr = np.array([midi_vals], dtype=np.int64)

    spk = r["spk"]

    # ── Step1: duration_linguistic ──
    enc_d, mask_d = sess["ling_dur"].run(None, {
        "tokens": tok_d, "languages": lng_d,
        "word_div": word_div_arr, "word_dur": word_dur_arr,
    })

    # ── Step2: dur_pred -> ph_dur(ticks), 按MIDI word_dur强制缩放对齐 ──
    ph_midi = midi_vals_arr
    spk_tok = np.broadcast_to(spk[np.newaxis, np.newaxis, :], (1, n_tok, 384)).astype(np.float32)
    ph_dur_pred = sess["dur"].run(None, {
        "encoder_out": enc_d, "x_masks": mask_d,
        "ph_midi": ph_midi, "spk_embed": spk_tok,
    })[0][0]  # (n_tok,)

    # 逐音符组: 预测权重 x MIDI时值 = 对齐后的frames (组内帧数和=音符时值, 零漂移)
    ph_dur_frames = np.zeros(n_tok, dtype=np.int64)
    idx = 0
    for i, wd in enumerate(word_div):
        target_f = max(wd * 2, int(round(word_dur[i] / tps * FPS)))
        g = ph_dur_pred[idx:idx + wd].astype(np.float64)
        gs = g.sum()
        w = (g / gs) if gs > 1e-6 else np.full(wd, 1.0 / wd)
        f = np.maximum(1, np.floor(w * target_f)).astype(np.int64)
        rem = target_f - int(f.sum())
        if rem != 0:
            f[int(np.argmax(w))] += rem  # 舍入残差补给主音素
        ph_dur_frames[idx:idx + wd] = f
        idx += wd
    n_frames = int(ph_dur_frames.sum())

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
    for nn, wd in zip(note_seq, word_div):
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
    ap.add_argument("--out", default=None, help="输出wav路径(默认 track/singer/{track}.wav)")
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

    # 线性对齐
    sections = ldata.get("lyric_sections", [])
    lyrics = align_lyrics_linear(midi_n, sections, BAR_SEGS, TPB)

    n_char = sum(1 for l in lyrics if l not in ("R", "-"))
    n_slur = sum(1 for l in lyrics if l == "-")
    n_rest = sum(1 for l in lyrics if l == "R")
    print("notes=%d chars=%d slur(-)=%d rest=%d" % (len(midi_n), n_char, n_slur, n_rest))
    # 保存对齐结果供检查
    with open(os.path.join(singer, "lyrics_match_v2.json"), "w", encoding="utf-8") as f:
        json.dump({"midi_notes": midi_n, "lyrics": lyrics, "bpm": args.bpm, "tpb": TPB},
                  f, ensure_ascii=False)

    # 预载模型(7个)
    load_res()
    opts = _res["opts"]
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

    print("synthesizing (7-step pipeline, segment-wise)...")
    audio = synth(midi_n, lyrics, sess, bpm=args.bpm)
    dur = len(audio) / SR_WRITE
    peak = float(np.max(np.abs(audio)))
    midi_dur = (midi_n[-1]["tick"] + midi_n[-1]["dur"]) / (TPB * args.bpm / 60.0)
    print("output: %.1fs (MIDI全长%.1fs, 漂移%.1f%%) peak=%.3f" % (
        dur, midi_dur, 100 * (dur - midi_dur) / midi_dur, peak))

    out = args.out or os.path.join(singer, args.track + ".wav")
    tmp = os.path.join(tempfile.gettempdir(), "__yunye7v2__.wav")
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
