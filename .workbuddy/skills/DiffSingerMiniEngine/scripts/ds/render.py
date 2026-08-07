# -*- coding: utf-8 -*-
"""render层: ustx.json plan -> wav

段调度(迁移自 v2, 保留资产):
- seg_id=None 段补零静音; sing 段整段推理(跳过dur, 用plan烘焙的ph_dur帧)
- 段时长用时间跨度(含音符间空隙); 输出长度与MIDI时值偏差>20ms才重采样吸收
- 头部静音按首个音符tick; 每段推理后 gc.collect() 防内存累积
本层新增(官方契约):
- SP padding 音频切除: 渲染链路全程含首尾各8帧padding, vocoder输出后切除
  8*hop=4096 samples/侧(卷积边界效应由padding吸收, 不切会多出0.19s)
- vocoder 采样率 != 写盘采样率时重采样
"""
import gc
import os
import shutil
import tempfile
import numpy as np
import scipy.signal as sps
import soundfile as sf

from .voicebank import HEAD_FRAMES, TAIL_FRAMES
from .predictors import segment_arrays, PitchPredictor, VariancePredictor
from .acoustic import AcousticRenderer


class Renderer:
    def __init__(self, vb, sess, steps_ac=20, steps_pitch=10, steps_var=20):
        self.vb = vb
        self.sess = sess
        self.pitch = PitchPredictor(vb, sess, steps_pitch)
        self.var = VariancePredictor(vb, sess, steps_var)
        self.ac = AcousticRenderer(vb, sess, steps_ac)
        self.sr = int(vb.cfg_voc.sample_rate)
        self.hop = int(vb.cfg_voc.hop_size)

    # ------------------------------------------------------------ 单段
    def render_chunk(self, plan_notes):
        """sing段 plan notes -> wav (已切除SP padding, 长度=body帧数*hop)"""
        seg = segment_arrays(plan_notes)
        midi = self.pitch.predict(seg)
        breath, voicing, tension = self.var.predict(seg, midi)
        mel, f0 = self.ac.render_mel(seg, midi, breath, voicing, tension)
        wav = self.ac.run_vocoder(mel, f0)
        head = HEAD_FRAMES * self.hop
        body = seg["n_body"] * self.hop
        if len(wav) >= head + body:
            wav = wav[head:head + body]
        else:  # 兜底: vocoder输出不足时只切头部
            wav = wav[head:]
        return wav

    # ------------------------------------------------------------ 全曲
    def synth_from_plan(self, plan):
        """plan -> 全曲 audio (与MIDI时间轴严格对齐)"""
        m = plan["meta"]
        tps = m["tpb"] * m["bpm"] / 60.0
        notes = plan["notes"]
        sr = self.sr

        chunks = []
        head_ticks = notes[0]["position"] if notes else 0
        if head_ticks > 0:
            head_sec = head_ticks / tps
            chunks.append(np.zeros(int(head_sec * sr), dtype=np.float32))
            print("  head silence: %.2fs" % head_sec)

        i = 0
        prev_end = notes[0]["position"] if notes else 0
        while i < len(notes):
            sid = notes[i].get("seg_id")
            j = i
            while j < len(notes) and notes[j].get("seg_id") == sid:
                j += 1
            group = notes[i:j]
            gap_ticks = group[0]["position"] - prev_end
            if gap_ticks > 0:
                # 段间空隙补静音, 保持与 MIDI 时间轴严格对齐(懒进场/呼吸口不塌陷)
                chunks.append(np.zeros(int(gap_ticks / tps * sr), dtype=np.float32))
            seg_ticks = group[-1]["position"] + group[-1]["duration"] - group[0]["position"]
            seg_sec = seg_ticks / tps
            prev_end = group[-1]["position"] + group[-1]["duration"]
            if sid is None:
                chunks.append(np.zeros(int(seg_sec * sr), dtype=np.float32))
                print("  notes %d-%d REST %.1fs -> silence" % (i, j, seg_sec))
            else:
                try:
                    wav = self.render_chunk(group)
                    target = int(seg_sec * sr)
                    if abs(len(wav) - target) > sr * 0.02:  # 偏差>20ms才修
                        wav = sps.resample(wav, target).astype(np.float32)
                    chunks.append(wav)
                    print("  notes %d-%d SING seg#%d %.1fs OK (chars=%d)" % (
                        i, j, sid, seg_sec,
                        sum(1 for pn in group if pn["kind"] == "sing")))
                except Exception as ex:
                    print("  notes %d-%d FAILED: %s" % (i, j, ex))
                    chunks.append(np.zeros(int(seg_sec * sr), dtype=np.float32))
            gc.collect()
            i = j

        return np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.float32)


def write_audio(audio, out, sr_write, sr_voc):
    """重采样(如需) -> 首尾淡入淡出 -> 写盘(临时文件中转) -> 峰值>0.891则归一化"""
    if abs(sr_voc - sr_write) > 100:
        target = int(len(audio) * sr_write / sr_voc)
        audio = sps.resample(audio, target).astype(np.float32)
    fi = min(int(0.05 * sr_write), len(audio) // 4)
    if fi > 0:
        audio[:fi] *= np.linspace(0, 1, fi)
    fo = min(int(0.1 * sr_write), len(audio) // 4)
    if fo > 0:
        audio[-fo:] *= np.linspace(1, 0, fo)

    peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
    tmp = os.path.join(tempfile.gettempdir(), "__ds_render__.wav")
    try:
        sf.write(tmp, audio, sr_write, subtype="PCM_16")
        if os.path.exists(out):
            os.remove(out)
        shutil.copy(tmp, out)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    if peak > 0.891:
        d, s = sf.read(out)
        sf.write(out, d * (0.891 / peak), s, subtype="PCM_16")
        print("normalized: %.3f -> 0.891" % peak)
    return peak
