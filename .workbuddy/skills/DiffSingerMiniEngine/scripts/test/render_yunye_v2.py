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
  5. 两段式plan/render: mid+歌词先固化为 track/singer/{track}.ustx.json
     (ustx风格中间工程文件: 每音符 position/duration/tone/lyric/kind/seg_id/phones帧分配,
     固化对齐/分段/间隙展开/音素/ph_dur全部渲染决策, 可审计可手改),
     再从plan渲染; --plan-only 只生成plan, --from-plan 从plan渲染(手改plan后可局部重渲染)
  6. variance链路独立化: dsvariance/dsconfig.yaml指定 variance_assets/variance_assets/ 下的
     独立linguistic+variance模型和独立音素表(19个键id与dur表不同), 误用duration_assets版本
     会导致breathiness/voicing/tension预测失真(水声)
  7. 各组件专属spk_embed: dsdur/dsvariance/dspitch/acoustic四个emb数值均不同,
     pitch是zhibin-pop训练必须用zhibin-pop.emb, 混喂会致f0曲线失真(NSF声码器水下咕噜声)
  8. acoustic depth=0.7 (dsconfig max_depth上限, 超上限扩散超分布, mel模糊)

Pipeline (与v1相同):
  1. duration_linguistic -> 2. dur -> 3. pitch_linguistic -> 4. pitch
  -> 5. variance -> 6. acoustic -> 7. vocoder
"""
import sys, os, json, yaml, argparse, tempfile, shutil
from datetime import datetime
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np, soundfile as sf, scipy.signal as sps
import mido, onnxruntime as ort

try:
    from pypinyin import pinyin, Style
    HAS_PYPINYIN = True
except ImportError:
    HAS_PYPINYIN = False

def load_env():
    """从工作区根 .env 读配置: singers_path(声库zip目录) / diff_singer_mini_engine_assets(资源目录)"""
    env = {}
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    p = os.path.join(root, ".env")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env

_ENV = load_env()


def find_vb(zip_name=None):
    """由声库zip名定位解压目录(OpenUTAU安装结构: singers_path同级/{stem}/{stem})"""
    sp = _ENV.get("singers_path", r"D:\OpenUtau\Singers\Singers")
    stem = (os.path.splitext(os.path.basename(zip_name))[0] if zip_name
            else "YunYe_DiffSinger_CE_26.07.16")
    cands = [
        os.path.join(os.path.dirname(sp), stem, stem),
        os.path.join(sp, stem, stem),
        os.path.join(os.path.dirname(sp), stem),
        os.path.join(sp, stem),
    ]
    for c in cands:
        if os.path.exists(os.path.join(c, "acoustic.onnx")):
            return c
    return cands[0]


VB = find_vb()
AC_PATH = os.path.join(VB, "acoustic.onnx")
VOC_PATH = os.path.join(VB, "dsvocoder", "2601_zhibin_club_ft_pc_nsf_hifigan.onnx")
LING_DUR = os.path.join(VB, "variance_assets", "duration_assets", "linguistic.onnx")
DUR_PATH = os.path.join(VB, "variance_assets", "duration_assets", "dur.onnx")
# variance用独立嵌套目录(dsvariance/dsconfig.yaml指定): 与dur是不同模型, 且音素表有19个键id不同
LING_VAR = os.path.join(VB, "variance_assets", "variance_assets", "linguistic.onnx")
VAR_PATH = os.path.join(VB, "variance_assets", "variance_assets", "variance.onnx")
PH_JSON_V = os.path.join(VB, "variance_assets", "variance_assets", "phonemes.json")
LANG_JSON_V = os.path.join(VB, "variance_assets", "variance_assets", "languages.json")
LING_PITCH = os.path.join(VB, "dspitch", "linguistic.onnx")
PITCH_PATH = os.path.join(VB, "dspitch", "pitch.onnx")
PH_JSON = os.path.join(VB, "phonemes.json")           # 219 (duration/acoustic/variance)
LANG_JSON = os.path.join(VB, "languages.json")
PH_JSON_P = os.path.join(VB, "dspitch", "phonemes.json")  # 74 (pitch)
LANG_JSON_P = os.path.join(VB, "dspitch", "languages.json")
DICT_ZH = os.path.join(VB, "dsdur", "dsdict-zh.yaml")
# 各组件专属spk_embed(实测4个emb数值均不同, 喂错致f0/方差失真)
EMB_PATH = os.path.join(VB, "yunye.emb")                      # acoustic 用
EMB_DUR = os.path.join(VB, "dsdur", "yunye.emb")             # dur 专用
EMB_VAR = os.path.join(VB, "dsvariance", "yunye.emb")        # variance 专用
EMB_PITCH = os.path.join(VB, "dspitch", "zhibin-pop.emb")    # pitch(zhibin-pop训练)专用

SR_WRITE = 44100
SR_VOC = 44100  # vocoder.yaml sample_rate=44100 (原44109为笔误, 致静音段长度+0.02%)
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
    with open(PH_JSON_V, encoding="utf-8") as f:
        ph_v = json.load(f)
    with open(LANG_JSON_V, encoding="utf-8") as f:
        lang_v = json.load(f)
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
    zh_v = lang_v["zh"]
    max_v_id = max(ph_v.values())
    for k, v in ph_v.items():
        if v >= max_v_id:
            ph_v[k] = max_v_id - 1

    # py -> [(ph_str, dur_id, pitch_id), ...]  保留音素字符串, 供plan烘焙层记录
    py2phs = {}
    for e in d.get("entries", []):
        py = e.get("grapheme", "")
        phs = e.get("phonemes", [])
        if isinstance(phs, str):
            phs = [phs]
        items = []
        ok = True
        for p in phs:
            did = ph.get(p)
            pid = ph_p.get(p)
            if did is None:
                ok = False
                break
            items.append((p, did, pid))
        if py and ok and items:
            py2phs[py] = items

    spk = np.fromfile(EMB_PATH, dtype=np.float32).astype(np.float32)
    spk_dur = np.fromfile(EMB_DUR, dtype=np.float32).astype(np.float32)
    spk_var = np.fromfile(EMB_VAR, dtype=np.float32).astype(np.float32)
    spk_pitch = np.fromfile(EMB_PITCH, dtype=np.float32).astype(np.float32)
    opts = ort.SessionOptions()
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    # 关闭内存池/内存模式缓存: 逐段推理时arena会持续累积不释放, 长曲后段必OOM
    opts.enable_cpu_mem_arena = False
    opts.enable_mem_pattern = False

    _res = {
        "ph": ph, "ph_p": ph_p, "lang": lang, "lang_p": lang_p,
        "zh": zh, "zh_p": zh_p, "zh_v": zh_v, "ph_v": ph_v,
        "py2phs": py2phs, "opts": opts,
        "spk": spk, "spk_dur": spk_dur, "spk_var": spk_var, "spk_pitch": spk_pitch,
    }
    print("  ph_dur=%d ph_pitch=%d ph_var=%d py2phs=%d" % (
        len(ph), len(ph_p), len(ph_v), len(py2phs)))


def lyric_phones(ch):
    """汉字 -> [(ph_str, dur_id, pitch_id, lang_d, lang_p), ...] (1~2个音素: 声母+韵母)"""
    r = _res
    sp = ("SP", r["ph"].get("SP", 4), r["ph_p"].get("SP", 4), r["zh"], r["zh_p"])
    if ch in ("R", "sp", "sil", "", "X", "…", "ҭ"):
        return [sp]
    if not HAS_PYPINYIN:
        return [sp]
    try:
        result = pinyin(ch, style=Style.NORMAL)
        p = result[0][0] if result and result[0] else None
    except Exception:
        p = None
    if not p:
        return [sp]
    if p in r["py2phs"]:
        return [(s, d_, p_, r["zh"], r["zh_p"]) for (s, d_, p_) in r["py2phs"][p]]
    return [sp]


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


# ---------------------------------------------------------------- plan 构建
def build_plan(midi_n, lyrics, sess, bpm, TPB, meta):
    """mid+歌词 -> ustx.json plan: 固化对齐/分段/间隙展开/音素/ph_dur帧 全部渲染决策。
    notes字段: position/duration/tone 同ustx; kind: sing|slur|rest|gap;
    seg_id: 推理段号(rest段为None); phones: [{ph,frames}] dur预测+时长约束后的烘焙结果"""
    load_res()
    r = _res
    tps = TPB * bpm / 60.0

    segs = split_segments(midi_n, lyrics, TPB, BAR_SEGS)
    print("  segments: %d (%s)" % (len(segs),
          " ".join("%s:%d-%d" % (k[0], a, b) for k, a, b in segs)))

    plan_notes = []
    seg_counter = 0
    for kind, a, b in segs:
        if kind == "rest":
            for i in range(a, b):
                nn = midi_n[i]
                frames = max(1, int(round(nn["dur"] / tps * FPS)))
                plan_notes.append({
                    "position": nn["tick"], "duration": nn["dur"], "tone": nn["note"],
                    "lyric": "R", "kind": "rest", "seg_id": None,
                    "phones": [{"ph": "SP", "frames": frames}], "word_frames": frames,
                })
            continue
        sn, sl = expand_gaps(midi_n[a:b], lyrics[a:b])
        chunk_notes = plan_chunk(sn, sl, sess, r, tps)
        for pn in chunk_notes:
            pn["seg_id"] = seg_counter
        plan_notes.extend(chunk_notes)
        print("  plan seg#%d midi_notes=%d-%d expanded=%d" % (seg_counter, a, b, len(sn)))
        seg_counter += 1
        import gc
        gc.collect()

    return {"format": "ustx-json", "version": 1, "meta": meta, "notes": plan_notes}


# ---------------------------------------------------------------- 渲染
def synth_from_plan(plan, sess):
    """ustx.json plan -> wav: seg_id=None段补零, sing段整段推理(跳过dur, 用烘焙ph_dur);
    输出与MIDI时间轴严格对齐"""
    load_res()
    r = _res
    m = plan["meta"]
    tps = m["tpb"] * m["bpm"] / 60.0
    notes = plan["notes"]

    # 头部静音(首个音符之前的MIDI时间)
    chunks = []
    head_ticks = notes[0]["position"] if notes else 0
    if head_ticks > 0:
        head_sec = head_ticks / tps
        chunks.append(np.zeros(int(head_sec * SR_VOC), dtype=np.float32))
        print("  head silence: %.2fs" % head_sec)

    i = 0
    while i < len(notes):
        sid = notes[i].get("seg_id")
        j = i
        while j < len(notes) and notes[j].get("seg_id") == sid:
            j += 1
        group = notes[i:j]
        # 段时长用时间跨度(含音符间空隙), 不是时值之和
        seg_ticks = group[-1]["position"] + group[-1]["duration"] - group[0]["position"]
        seg_sec = seg_ticks / tps
        if sid is None:
            chunks.append(np.zeros(int(seg_sec * SR_VOC), dtype=np.float32))
            print("  notes %d-%d REST %.1fs -> silence" % (i, j, seg_sec))
        else:
            try:
                wav = render_chunk(group, sess, r)
                # 严格对齐: 输出长度必须 = MIDI 时值(帧级误差用重采样吸收)
                target = int(seg_sec * SR_VOC)
                if abs(len(wav) - target) > SR_VOC * 0.02:  # 偏差>20ms才修
                    wav = sps.resample(wav, target).astype(np.float32)
                chunks.append(wav)
                print("  notes %d-%d SING seg#%d %.1fs OK (chars=%d)" % (
                    i, j, sid, seg_sec, sum(1 for pn in group if pn["kind"] == "sing")))
            except Exception as ex:
                print("  notes %d-%d FAILED: %s" % (i, j, ex))
                chunks.append(np.zeros(int(seg_sec * SR_VOC), dtype=np.float32))
        import gc
        gc.collect()  # 每段后释放推理中间结果
        i = j

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


def plan_chunk(notes, lyrics, sess, r, tps):
    """sing段plan: 构建音素token('-'继承前字韵母) + dur预测 + ph_dur按MIDI时值强制缩放,
    烘焙为每音符 phones:[{ph,frames}] 写进plan"""
    tok_d, tok_p, lng_d, lng_p, midi_vals = [], [], [], [], []
    word_div, word_dur = [], []
    entries = []  # (note, lyric, kind, seq)

    last_seq = None  # 前字音素序列, 供'-'继承韵母
    for nn, ly in zip(notes, lyrics):
        is_rest = (ly == "R")
        if ly == "R":
            kind = "gap" if nn["note"] == 0 else "rest"
        elif ly == "-":
            kind = "slur"
        else:
            kind = "sing"
        if ly == "-" and last_seq:
            seq = [last_seq[-1]]  # 只延续韵母
        else:
            seq = lyric_phones(ly)
            if ly not in ("-", "R"):
                # 仅真实汉字更新last_seq; R(含gap)的SP不能污染'-'的韵母继承
                # (v2 bug: 间隙展开后 '-' 继承到SP, 69/72拖腔变静音)
                last_seq = seq
        entries.append((nn, ly, kind, seq))
        word_div.append(len(seq))
        word_dur.append(int(nn["dur"]))
        for phs, did, pid, ldid, lpid in seq:
            tok_d.append(did)
            tok_p.append(pid)
            lng_d.append(ldid)
            lng_p.append(lpid)
            midi_vals.append(0 if is_rest else nn["note"])

    n_tok = len(tok_d)
    tok_d = np.array([tok_d], dtype=np.int64)
    lng_d = np.array([lng_d], dtype=np.int64)
    word_div_arr = np.array([word_div], dtype=np.int64)
    word_dur_arr = np.array([word_dur], dtype=np.int64)
    midi_vals_arr = np.array([midi_vals], dtype=np.int64)

    spk = r["spk_dur"]  # dur用dsdur专属emb

    # ── Step1: duration_linguistic ──
    enc_d, mask_d = sess["ling_dur"].run(None, {
        "tokens": tok_d, "languages": lng_d,
        "word_div": word_div_arr, "word_dur": word_dur_arr,
    })

    # ── Step2: dur_pred -> ph_dur(ticks), 按MIDI word_dur强制缩放对齐 ──
    spk_tok = np.broadcast_to(spk[np.newaxis, np.newaxis, :], (1, n_tok, 384)).astype(np.float32)
    ph_dur_pred = sess["dur"].run(None, {
        "encoder_out": enc_d, "x_masks": mask_d,
        "ph_midi": midi_vals_arr, "spk_embed": spk_tok,
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

    # 烘焙进plan notes
    plan_notes = []
    idx = 0
    for (nn, ly, kind, seq), wd in zip(entries, word_div):
        frames = ph_dur_frames[idx:idx + wd]
        phones = [{"ph": seq[k][0], "frames": int(frames[k])} for k in range(wd)]
        plan_notes.append({
            "position": nn["tick"], "duration": nn["dur"], "tone": nn["note"],
            "lyric": ly, "kind": kind,
            "phones": phones, "word_frames": int(frames.sum()),
        })
        idx += wd
    return plan_notes


def render_chunk(plan_notes, sess, r):
    """从plan烘焙数据渲染sing段: 跳过dur预测(直接用plan的ph_dur帧),
    variance_linguistic -> pitch_linguistic -> pitch -> variance -> acoustic -> vocoder"""
    tok_d, tok_p, tok_v, lng_d, lng_p, lng_v = [], [], [], [], [], []
    ph_dur_list, word_div, word_dur = [], [], []
    note_is_rest, note_dur_frames = [], []
    sp_d, sp_p = r["ph"].get("SP", 4), r["ph_p"].get("SP", 4)
    sp_v = r["ph_v"].get("SP", 4)

    for pn in plan_notes:
        is_rest = pn["kind"] in ("rest", "gap")
        phones = pn["phones"]
        word_div.append(len(phones))
        word_dur.append(int(pn["duration"]))
        note_is_rest.append(is_rest)
        note_dur_frames.append(int(pn["word_frames"]))
        for it in phones:
            tok_d.append(r["ph"].get(it["ph"], sp_d))
            tok_p.append(r["ph_p"].get(it["ph"], sp_p))
            tok_v.append(r["ph_v"].get(it["ph"], sp_v))
            lng_d.append(r["zh"])
            lng_p.append(r["zh_p"])
            lng_v.append(r["zh_v"])
            ph_dur_list.append(int(it["frames"]))

    n_tok = len(tok_d)
    ph_dur_frames = np.array(ph_dur_list, dtype=np.int64)
    n_frames = int(ph_dur_frames.sum())
    tok_d = np.array([tok_d], dtype=np.int64)
    tok_p = np.array([tok_p], dtype=np.int64)
    tok_v = np.array([tok_v], dtype=np.int64)
    lng_d = np.array([lng_d], dtype=np.int64)
    lng_p = np.array([lng_p], dtype=np.int64)
    lng_v = np.array([lng_v], dtype=np.int64)
    word_div_arr = np.array([word_div], dtype=np.int64)
    word_dur_arr = np.array([word_dur], dtype=np.int64)

    spk = r["spk"]  # acoustic用根emb
    spk_pitch = r["spk_pitch"]
    spk_var = r["spk_var"]

    # ── variance_linguistic (variance专用encoder: 独立模型+独立音素表, 输入ph_dur) ──
    enc_v, mask_v = sess["ling_var"].run(None, {
        "tokens": tok_v, "languages": lng_v,
        "ph_dur": ph_dur_frames.reshape(1, -1),
    })

    # ── Step3: pitch_linguistic ──
    enc_p, mask_p = sess["ling_p"].run(None, {
        "tokens": tok_p, "languages": lng_p,
        "ph_dur": ph_dur_frames.reshape(1, -1),
    })

    # ── Step4: pitch_pred -> midi值 ──
    note_midi = np.array([[float(0 if rest else pn["tone"]) for pn, rest in zip(plan_notes, note_is_rest)]], dtype=np.float32)
    note_rest = np.array([note_is_rest], dtype=bool)
    note_dur = np.array([note_dur_frames], dtype=np.int64)

    pitch_in = np.zeros((1, n_frames), dtype=np.float32)
    expr = np.zeros((1, n_frames), dtype=np.float32)
    retake_p = np.ones((1, n_frames), dtype=bool)
    spk_fr = np.broadcast_to(spk[np.newaxis, np.newaxis, :], (1, n_frames, 384)).astype(np.float32)
    spk_fr_p = np.broadcast_to(spk_pitch[np.newaxis, np.newaxis, :], (1, n_frames, 384)).astype(np.float32)
    spk_fr_v = np.broadcast_to(spk_var[np.newaxis, np.newaxis, :], (1, n_frames, 384)).astype(np.float32)
    pitch_pred_midi = sess["pitch"].run(None, {
        "encoder_out": enc_p, "ph_dur": ph_dur_frames.reshape(1, -1),
        "note_midi": note_midi, "note_rest": note_rest, "note_dur": note_dur,
        "pitch": pitch_in, "expr": expr, "retake": retake_p, "spk_embed": spk_fr_p,
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
        "encoder_out": enc_v, "ph_dur": ph_dur_frames.reshape(1, -1),
        "pitch": f0,
        "breathiness": np.zeros((1, n_frames), dtype=np.float32),
        "voicing": np.ones((1, n_frames), dtype=np.float32),
        "tension": np.zeros((1, n_frames), dtype=np.float32),
        "retake": retake_v, "spk_embed": spk_fr_v,
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
        "depth": np.array(0.7, dtype=np.float32),  # dsconfig max_depth=0.7, 超上限劣化mel质量(水声主因之一)
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
    ap.add_argument("--plan", dest="plan_path", default=None,
                    help="ustx.json路径(默认 track/singer/{track}.ustx.json)")
    ap.add_argument("--plan-only", action="store_true",
                    help="只生成 {track}.ustx.json, 不渲染")
    ap.add_argument("--from-plan", action="store_true",
                    help="跳过plan生成, 从已有 {track}.ustx.json 渲染(手改plan后可重渲染)")
    args = ap.parse_args()

    proj = os.path.join("workspace", "project", args.project)
    singer = os.path.join(proj, "song_engineer", "track", "singer")
    os.makedirs(singer, exist_ok=True)
    plan_path = args.plan_path or os.path.join(singer, args.track + ".ustx.json")

    # 预载模型(8个), VB由.env singers_path推导
    print("  voicebank: %s" % VB)
    load_res()
    opts = _res["opts"]
    prov = ["CPUExecutionProvider"]
    print("  loading models...")
    sess = {
        "ling_dur": ort.InferenceSession(LING_DUR, opts, providers=prov),
        "dur": ort.InferenceSession(DUR_PATH, opts, providers=prov),
        "ling_var": ort.InferenceSession(LING_VAR, opts, providers=prov),
        "var": ort.InferenceSession(VAR_PATH, opts, providers=prov),
        "ling_p": ort.InferenceSession(LING_PITCH, opts, providers=prov),
        "pitch": ort.InferenceSession(PITCH_PATH, opts, providers=prov),
        "ac": ort.InferenceSession(AC_PATH, opts, providers=prov),
        "voc": ort.InferenceSession(VOC_PATH, opts, providers=prov),
    }
    print("  models loaded (8)")

    if args.from_plan:
        # 从已有plan渲染(手改ustx.json后重渲染)
        with open(plan_path, encoding="utf-8") as f:
            plan = json.load(f)
        print("plan loaded: %s (notes=%d)" % (plan_path, len(plan["notes"])))
    else:
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

        # 构建plan: 固化对齐/分段/间隙展开/音素/ph_dur帧全部渲染决策到 ustx.json
        meta = {
            "name": args.track, "project": args.project,
            "bpm": args.bpm, "tpb": TPB, "fps": FPS,
            "sample_rate": SR_WRITE, "hop_size": 512,
            "singer": "yunye", "voicebank": VB,
            "models": {
                "ling_dur": LING_DUR, "dur": DUR_PATH, "variance": VAR_PATH,
                "ling_pitch": LING_PITCH, "pitch": PITCH_PATH,
                "acoustic": AC_PATH, "vocoder": VOC_PATH,
            },
            "bar_segs": BAR_SEGS,
            "sources": {"mid": mp, "lyrics": lj},
            "generator": "render_yunye_v2.py 7-step pipeline",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        print("building plan (align+segment+phoneme+dur bake)...")
        plan = build_plan(midi_n, lyrics, sess, args.bpm, TPB, meta)
        with open(plan_path, "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=1)
        print("plan saved: %s (notes=%d)" % (plan_path, len(plan["notes"])))
        if args.plan_only:
            return

    print("synthesizing (7-step pipeline, from plan)...")
    audio = synth_from_plan(plan, sess)
    m = plan["meta"]
    dur = len(audio) / SR_WRITE
    peak = float(np.max(np.abs(audio)))
    last = plan["notes"][-1]
    midi_dur = (last["position"] + last["duration"]) / (m["tpb"] * m["bpm"] / 60.0)
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
