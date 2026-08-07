# -*- coding: utf-8 -*-
"""预测器层: PitchPredictor / VariancePredictor (复刻 OpenUTAU 官方输入契约)

致命契约(v1-v5 水声根因, 全部在此修复):
- pitch 模型: pitch 初值全 60.0; expr 全 1.0(0.0=表现力归零); note_midi 用 plan 固化的
  rest填充值(note_midi_filled); 首尾各 pad 1 个 rest note(8帧, midi=边缘音符填充值)
- variance 模型: pitch 输入 = **midi 值**(不是 Hz); breathiness/voicing/tension 初值全 0;
  retake (1,n_frames,3) 全 true
- 所有 linguistic: tokens 首尾各 pad 1 个 SP(8帧); languages padding=0;
  ph 模式(predict_dur=false)直接传 padded ph_dur
- spk_embed: pitch 用 dspitch 的 emb, variance 用 dsvariance 的 emb(混喂致失真)
输出均为**含padding**的帧曲线(padded = body + 16帧), padding音频在 render 层切除。
"""
import numpy as np

from .voicebank import HEAD_FRAMES, TAIL_FRAMES


def segment_arrays(plan_notes):
    """plan sing段 -> 帧/音符级数组 (body + SP padding)
    返回 dict: body_phones, ph_dur(padded), note_midi/note_rest/note_dur(padded),
    n_body, n_frames"""
    body_phones = []
    ph_dur_body = []
    note_dur_body = []
    note_midi_body = []
    note_rest_body = []
    for pn in plan_notes:
        for p in pn["phones"]:
            body_phones.append(p["ph"])
            ph_dur_body.append(int(p["frames"]))
        note_dur_body.append(int(pn["word_frames"]))
        note_midi_body.append(float(pn["note_midi_filled"]))
        # 官方: slur 继承前一音符(含插入的gap)的 rest 状态
        if pn["kind"] == "slur" and note_rest_body:
            note_rest_body.append(note_rest_body[-1])
        else:
            note_rest_body.append(pn["kind"] in ("rest", "gap"))

    ph_dur = np.array([HEAD_FRAMES] + ph_dur_body + [TAIL_FRAMES], dtype=np.int64)
    note_dur = np.array([HEAD_FRAMES] + note_dur_body + [TAIL_FRAMES], dtype=np.int64)
    note_midi = np.array([note_midi_body[0]] + note_midi_body + [note_midi_body[-1]],
                         dtype=np.float32)
    note_rest = np.array([True] + note_rest_body + [True], dtype=bool)
    n_frames = int(ph_dur.sum())
    assert int(note_dur.sum()) == n_frames, "note_dur/ph_dur 帧数不一致"
    return {
        "body_phones": body_phones,
        "ph_dur": ph_dur,
        "note_midi": note_midi,
        "note_rest": note_rest,
        "note_dur": note_dur,
        "n_body": int(sum(ph_dur_body)),
        "n_frames": n_frames,
    }


def pad_tokens(tab, body_phones):
    """官方: tokens = [SP] + body + [SP]; languages = [0] + 按音素前缀 + [0]"""
    tokens = [tab.token("SP")] + [tab.token(p) for p in body_phones] + [tab.token("SP")]
    langs = [0] + [tab.lang_id(p) for p in body_phones] + [0]
    return (np.array([tokens], dtype=np.int64), np.array([langs], dtype=np.int64))


def _spk_frames(emb, n_frames):
    return np.broadcast_to(emb[np.newaxis, np.newaxis, :],
                           (1, n_frames, emb.shape[0])).astype(np.float32)


class PitchPredictor:
    """dspitch: ph 模式 linguistic + pitch 扩散模型 -> midi 曲线 (padded)"""

    def __init__(self, vb, sess, steps=10, expr=1.0):
        self.vb = vb
        self.sess = sess
        self.steps = int(steps)  # 官方默认 DiffSingerStepsPitch=10
        self.expr = float(expr)  # 表现力初值(0=表现力归零), 可由 voice_conf 覆盖

    def predict(self, seg):
        tokens, langs = pad_tokens(self.vb.tab_pitch, seg["body_phones"])
        enc, _mask = self.sess["ling_p"].run(None, {
            "tokens": tokens, "languages": langs,
            "ph_dur": seg["ph_dur"].reshape(1, -1),
        })
        n = seg["n_frames"]
        out = self.sess["pitch"].run(None, {
            "encoder_out": enc,
            "ph_dur": seg["ph_dur"].reshape(1, -1),
            "note_midi": seg["note_midi"].reshape(1, -1),
            "note_rest": seg["note_rest"].reshape(1, -1),
            "note_dur": seg["note_dur"].reshape(1, -1),
            "pitch": np.full((1, n), 60.0, dtype=np.float32),   # 官方初值 60
            "expr": np.full((1, n), self.expr, dtype=np.float32),  # 表现力初值, 可配
            "retake": np.ones((1, n), dtype=bool),
            "spk_embed": _spk_frames(self.vb.emb_pitch, n),
            "steps": np.array(self.steps, dtype=np.int64),
        })[0]
        midi = np.asarray(out, dtype=np.float32).reshape(1, -1)
        body = midi[0, HEAD_FRAMES:HEAD_FRAMES + seg["n_body"]]
        print("    pitch: midi body min=%.1f max=%.1f mean=%.1f std=%.2f (steps=%d)" % (
            float(body.min()), float(body.max()), float(body.mean()),
            float(body.std()), self.steps))
        return midi


class VariancePredictor:
    """dsvariance: ph 模式 linguistic + variance 扩散模型 -> breathiness/voicing/tension"""

    def __init__(self, vb, sess, steps=20, breathiness=0.0, voicing=0.0, tension=0.0):
        self.vb = vb
        self.sess = sess
        self.steps = int(steps)  # 官方默认 DiffSingerStepsVariance=20
        # variance 初值, 可由 voice_conf 覆盖(决定整体气声/张力性格)
        self.breathiness = float(breathiness)
        self.voicing = float(voicing)
        self.tension = float(tension)

    def predict(self, seg, pitch_midi):
        """pitch_midi: (1, n_frames) **midi 值**(不是 Hz)"""
        tokens, langs = pad_tokens(self.vb.tab_var, seg["body_phones"])
        enc, _mask = self.sess["ling_var"].run(None, {
            "tokens": tokens, "languages": langs,
            "ph_dur": seg["ph_dur"].reshape(1, -1),
        })
        n = seg["n_frames"]
        outs = self.sess["var"].run(None, {
            "encoder_out": enc,
            "ph_dur": seg["ph_dur"].reshape(1, -1),
            "pitch": pitch_midi.astype(np.float32),              # 官方: midi 值
            "breathiness": np.full((1, n), self.breathiness, dtype=np.float32),
            "voicing": np.full((1, n), self.voicing, dtype=np.float32),
            "tension": np.full((1, n), self.tension, dtype=np.float32),
            "retake": np.ones((1, n, 3), dtype=bool),
            "spk_embed": _spk_frames(self.vb.emb_var, n),
            "steps": np.array(self.steps, dtype=np.int64),
        })
        breath, voicing, tension = (np.asarray(o, dtype=np.float32).reshape(1, -1)
                                    for o in outs[:3])
        h = HEAD_FRAMES
        b = seg["n_body"]
        print("    variance: breath[%.1f,%.1f] voicing[%.1f,%.1f] tension[%.1f,%.1f] (steps=%d)" % (
            float(breath[0, h:h + b].min()), float(breath[0, h:h + b].max()),
            float(voicing[0, h:h + b].min()), float(voicing[0, h:h + b].max()),
            float(tension[0, h:h + b].min()), float(tension[0, h:h + b].max()),
            self.steps))
        return breath, voicing, tension
