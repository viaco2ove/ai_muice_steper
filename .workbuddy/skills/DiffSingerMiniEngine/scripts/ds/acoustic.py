# -*- coding: utf-8 -*-
"""acoustic + vocoder (官方契约):
- f0 = 440*2^((midi-69)/12) Hz; rest 帧**不归零**(pitch predictor 在填充音高引导下输出
  连续过渡曲线, 静音由 voicing/mel 先验决定; 强制归零会致 NSF 声码器水声)
- breathiness/voicing clamp [-96,0], tension clamp [-10,10] (对数域语义)
- gender=0, velocity=1.0; spk_embed=根 emb
- depth = min(1.0, dsconfig.max_depth) = 0.7 (官方 Preferences 默认1.0被max_depth截断)
- steps=20 (官方 DiffSingerSteps 默认)
- mel_base 与 vocoder 不一致时转换: 10->e 乘 2.30259, e->10 乘 0.434294
- vocoder: mel + f0(Hz); 输出采样率以 vocoder.yaml 为准
"""
import os

import numpy as np

from .predictors import pad_tokens, _spk_frames
from .voicebank import HEAD_FRAMES

# 性别/共振峰偏移 (官方 GENC 曲线: -1~+1, 正=偏厚实男声, 负=偏柔女声; 默认0)
# 实验用环境变量 DS_GENDER 覆盖, 如 DS_GENDER=0.2 把高音区的音色往男声压
GENDER = float(os.environ.get("DS_GENDER", "0"))


def midi_to_hz(midi):
    """官方 ToneToFreq: 440*2^((midi-69)/12); 不做 rest 归零"""
    return 440.0 * np.power(2.0, (np.asarray(midi, dtype=np.float64) - 69.0) / 12.0)


class AcousticRenderer:
    def __init__(self, vb, sess, steps=20):
        self.vb = vb
        self.sess = sess
        self.steps = int(steps)
        self.depth = float(min(1.0, vb.cfg_ac.max_depth))

    def render_mel(self, seg, pitch_midi, breath, voicing, tension):
        """-> (mel, f0Hz) 均为 padded 帧"""
        vb = self.vb
        tokens, langs = pad_tokens(vb.tab_ac, seg["body_phones"])
        n = seg["n_frames"]
        f0 = midi_to_hz(pitch_midi).astype(np.float32)
        breath = np.clip(breath, -96.0, 0.0).astype(np.float32)
        voicing = np.clip(voicing, -96.0, 0.0).astype(np.float32)
        tension = np.clip(tension, -10.0, 10.0).astype(np.float32)

        mel = self.sess["ac"].run(None, {
            "tokens": tokens, "languages": langs,
            "durations": seg["ph_dur"].reshape(1, -1),
            "f0": f0,
            "breathiness": breath, "voicing": voicing, "tension": tension,
            "gender": np.full((1, n), GENDER, dtype=np.float32),
            "velocity": np.ones((1, n), dtype=np.float32),
            "spk_embed": _spk_frames(vb.emb_ac, n),
            "depth": np.array(self.depth, dtype=np.float32),
            "steps": np.array(self.steps, dtype=np.int64),
        })[0].astype(np.float32)

        # 输出形状兜底: (1, n_mel, n_frames) -> (1, n_frames, n_mel)
        if mel.ndim == 3 and mel.shape[1] == vb.cfg_ac.num_mel_bins \
                and mel.shape[2] == n:
            mel = mel.transpose(0, 2, 1)

        # mel_base 转换 (云也: acoustic=e, vocoder=e -> 无需转换)
        ac_base, voc_base = vb.cfg_ac.mel_base, vb.cfg_voc.mel_base
        if ac_base != voc_base:
            factor = 2.30259 if (ac_base == "10" and voc_base == "e") else 0.434294
            mel = (mel * factor).astype(np.float32)
            print("    mel_base %s->%s (x%.5f)" % (ac_base, voc_base, factor))
        h = HEAD_FRAMES
        b = seg["n_body"]
        print("    acoustic: f0 body[%.1f,%.1f]Hz mel body[%.2f,%.2f] depth=%.2g steps=%d gender=%.2f" % (
            float(f0[0, h:h + b].min()), float(f0[0, h:h + b].max()),
            float(mel[0, h:h + b].min()), float(mel[0, h:h + b].max()),
            self.depth, self.steps, GENDER))
        return mel, f0

    def run_vocoder(self, mel, f0):
        """mel + f0(Hz) -> wav (padded, 采样率=vocoder.yaml)"""
        wav = self.sess["voc"].run(None, {
            "mel": mel.astype(np.float32), "f0": f0.astype(np.float32),
        })[0]
        return wav.flatten().astype(np.float32)
