# -*- coding: utf-8 -*-
"""plan层: mid+歌词 -> ustx.json (固化对齐/分段/音素/ph_dur帧/rest音高填充全部渲染决策)

官方契约(本模块承担的部分):
- dur linguistic 为 word 模式(predict_dur=true): tokens 首尾各 pad 1 个 SP,
  word_div 按元音位置切分(SP/AP=元音, 声母依附前一元音组, 首组含headSP/尾组含tailSP),
  word_dur = 组内 ph_dur **帧数**之和(不是MIDI ticks)
- rest 音符 note_midi 用邻近非 rest 音高填充: 组首用后值/组尾用前值/组中前后各半,
  全 rest 填 60; slur 继承前音符 rest 状态 -> 固化为 notes[].note_midi_filled
- dur 预测后按 MIDI 音符时值强制缩放(保留资产: 组内帧数和=音符时值, 零漂移)
SP padding 只进模型输入, 不写进 plan(渲染时动态加, 渲染后切除)。
"""
import gc
import numpy as np

from .align import split_segments, expand_gaps, BAR_SEGS
from .g2p import G2P
from .voicebank import HEAD_FRAMES, TAIL_FRAMES


def note_frames(dur_ticks, tps, fps):
    """MIDI时值ticks -> 帧数 (至少1帧)"""
    return max(1, int(round(dur_ticks / tps * fps)))


def fill_rest_midi(tones, rests):
    """官方 DiffSingerPitch: rest 音符用邻近非 rest 音高填充
    组首(i=0)全填后值; 组尾全填前值; 中间组 mid=(i+j+1)//2 分界前填前值后填后值; 全rest填60"""
    n = len(tones)
    out = [float(t) for t in tones]
    if n == 0:
        return out
    if all(rests):
        return [60.0] * n
    i = 0
    while i < n:
        if not rests[i]:
            i += 1
            continue
        j = i
        while j < n and rests[j]:
            j += 1
        if i == 0:
            for k in range(i, j):
                out[k] = float(tones[j])
        elif j == n:
            for k in range(i, j):
                out[k] = float(tones[i - 1])
        else:
            mid = (i + j + 1) // 2
            for k in range(i, mid):
                out[k] = float(tones[i - 1])
            for k in range(mid, j):
                out[k] = float(tones[j])
        i = j
    return out


def padded_word_div_dur(body_phones, ph_dur_padded, is_vowel):
    """官方 PaddedWordDivAndDur: word_div 按元音位置切分(首组+1含headSP, 尾组+1含tailSP),
    word_dur = 组内 padded ph_dur 帧数之和。body_phones: [ph_str]; ph_dur_padded: len=body+2"""
    n = len(body_phones)
    vowel_ids = [i for i, ph in enumerate(body_phones) if is_vowel(ph)]
    if not vowel_ids:
        vowel_ids = [n - 1]
    word_div = [vowel_ids[0] + 1]
    word_div += [b - a for a, b in zip(vowel_ids, vowel_ids[1:])]
    word_div.append(n - vowel_ids[-1] + 1)
    assert sum(word_div) == n + 2, "word_div sums to padded length"
    word_dur, off = [], 0
    for d in word_div:
        word_dur.append(int(sum(ph_dur_padded[off:off + d])))
        off += d
    return word_div, word_dur


class PlanBuilder:
    def __init__(self, vb, sess):
        self.vb = vb
        self.sess = sess
        self.g2p = G2P(vb)
        self.fps = vb.cfg_ac.fps

    # ------------------------------------------------------------ 顶层
    def build(self, midi_notes, lyrics, bpm, tpb, meta, bar_segs=None):
        """-> plan dict (ustx-json)。notes: position/duration/tone/lyric/kind/seg_id/
        phones[{ph,frames}]/word_frames/note_midi_filled"""
        tps = tpb * bpm / 60.0
        segs = split_segments(midi_notes, lyrics, tpb, bar_segs or BAR_SEGS)
        print("  segments: %d (%s)" % (len(segs),
              " ".join("%s:%d-%d" % (k[0], a, b) for k, a, b in segs)))

        plan_notes = []
        seg_id = 0
        for kind, a, b in segs:
            if kind == "rest":
                for i in range(a, b):
                    nn = midi_notes[i]
                    fr = note_frames(nn["dur"], tps, self.fps)
                    plan_notes.append({
                        "position": nn["tick"], "duration": nn["dur"], "tone": nn["note"],
                        "lyric": "R", "kind": "rest", "seg_id": None,
                        "phones": [{"ph": "SP", "frames": fr}], "word_frames": fr,
                        "note_midi_filled": float(nn["note"]),
                    })
                continue
            sn, sl = expand_gaps(midi_notes[a:b], lyrics[a:b])
            chunk = self._plan_chunk(sn, sl, tps)
            for pn in chunk:
                pn["seg_id"] = seg_id
            plan_notes.extend(chunk)
            print("  plan seg#%d midi_notes=%d-%d expanded=%d frames=%d" % (
                seg_id, a, b, len(sn), sum(pn["word_frames"] for pn in chunk)))
            seg_id += 1
            gc.collect()

        return {"format": "ustx-json", "version": 2, "meta": meta, "notes": plan_notes}

    # ------------------------------------------------------------ sing段
    def _plan_chunk(self, notes, lyrics, tps):
        vb, g2p = self.vb, self.g2p

        # 1) 音符->音素序列 (slur继承前字韵母; R的SP不污染继承链)
        entries = []  # (note, lyric, kind, [ph_str])
        last_seq = None
        for nn, ly in zip(notes, lyrics):
            if ly == "R":
                kind = "gap" if nn["note"] == 0 else "rest"
            elif ly == "-":
                kind = "slur"
            else:
                kind = "sing"
            if ly == "-" and last_seq:
                seq = g2p.slur_phones(last_seq)
            else:
                seq = g2p.lyric_phones(ly)
                if ly not in ("-", "R"):
                    last_seq = seq
            entries.append((nn, ly, kind, seq))

        # 2) 估计 ph_dur (dur linguistic 的 word_dur 特征用, 帧数语义)
        body_phones, est_dur, ph_midi = [], [], []
        for nn, ly, kind, seq in entries:
            nf = note_frames(nn["dur"], tps, self.fps)
            k = len(seq)
            per = [nf // k] * k
            per[-1] += nf - sum(per)
            m = 0 if kind in ("rest", "gap") else int(nn["note"])
            for j, ph in enumerate(seq):
                body_phones.append(ph)
                est_dur.append(per[j])
                ph_midi.append(m)

        # 3) SP padding (官方: tokens首尾各1个SP=8帧; languages padding=0; ph_midi取边缘音高)
        tab = vb.tab_dur
        head_m = int(notes[0]["note"]) or 60
        tail_m = int(notes[-1]["note"]) or 60
        tokens = [tab.token("SP")] + [tab.token(p) for p in body_phones] + [tab.token("SP")]
        langs = [0] + [tab.lang_id(p) for p in body_phones] + [0]
        est_padded = [HEAD_FRAMES] + est_dur + [TAIL_FRAMES]
        midi_padded = [head_m] + ph_midi + [tail_m]

        # 4) word_div/word_dur (官方元音分组)
        word_div, word_dur = padded_word_div_dur(body_phones, est_padded, vb.is_vowel)

        # 5) dur linguistic (word 模式)
        enc, mask = self.sess["ling_dur"].run(None, {
            "tokens": np.array([tokens], dtype=np.int64),
            "languages": np.array([langs], dtype=np.int64),
            "word_div": np.array([word_div], dtype=np.int64),
            "word_dur": np.array([word_dur], dtype=np.int64),
        })

        # 6) dur 预测 (spk_embed=dsdur专属emb, 按token广播)
        n_tok = len(tokens)
        spk = np.broadcast_to(vb.emb_dur[np.newaxis, np.newaxis, :],
                              (1, n_tok, vb.emb_dur.shape[0])).astype(np.float32)
        pred = self.sess["dur"].run(None, {
            "encoder_out": enc, "x_masks": mask,
            "ph_midi": np.array([midi_padded], dtype=np.int64),
            "spk_embed": spk,
        })[0][0]
        pred_body = np.asarray(pred[1:-1], dtype=np.float64)  # 丢弃padding预测

        # 7) 按MIDI音符时值强制缩放 (保留资产: 组内帧数和=音符时值, 零漂移)
        ph_frames = np.zeros(len(body_phones), dtype=np.int64)
        idx = 0
        for nn, ly, kind, seq in entries:
            k = len(seq)
            target = max(k * 2, note_frames(nn["dur"], tps, self.fps))
            g = pred_body[idx:idx + k]
            gs = g.sum()
            w = (g / gs) if gs > 1e-6 else np.full(k, 1.0 / k)
            f = np.maximum(1, np.floor(w * target)).astype(np.int64)
            rem = target - int(f.sum())
            if rem != 0:
                f[int(np.argmax(w))] += rem  # 舍入残差补给主音素
            ph_frames[idx:idx + k] = f
            idx += k

        # 8) rest 音高填充 (官方组填充, slur继承前音符rest状态)
        rests = []
        for nn, ly, kind, seq in entries:
            if kind == "slur" and rests:
                rests.append(rests[-1])
            else:
                rests.append(kind in ("rest", "gap"))
        filled = fill_rest_midi([nn["note"] for nn, *_ in entries], rests)

        # 9) 烘焙 plan notes
        plan_notes = []
        idx = 0
        for k, ((nn, ly, kind, seq), midi_f) in enumerate(zip(entries, filled)):
            kk = len(seq)
            frames = ph_frames[idx:idx + kk]
            plan_notes.append({
                "position": nn["tick"], "duration": nn["dur"], "tone": nn["note"],
                "lyric": ly, "kind": kind,
                "phones": [{"ph": seq[j], "frames": int(frames[j])} for j in range(kk)],
                "word_frames": int(frames.sum()),
                "note_midi_filled": float(midi_f),
            })
            idx += kk
        return plan_notes
