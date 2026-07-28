# -*- coding: utf-8 -*-
"""
generate_ambient_noise.py - 生成《走在》自然白噪音轨 wav

读 11_自然白噪音.json,按 note 的 technique + chord + duration + beat_pos
在指定小节区间生成对应的"环境白噪音"片段(粉噪+滤波+包络),
输出与歌曲同时长的 wav (BPM68, 4/4, 52 小节 ≈ 183.5s),用于覆盖 11_自然白噪音
在 FluidSynth 渲染时的静音。

技术分类(对应 technique 字段):
- 雨声 / 雨声淡入 / 雨声淡出: 粉噪(pink noise) + 低通滤波(cutoff≈8kHz),模拟细密雨滴
- 风声 / 风声淡入 / 风声淡出: 粉噪 + 带通滤波(200~1500Hz) + 缓慢 LFO 调制,模拟空旷风声
- 远处声 / 远处日常声: 粉噪 + 低通(600Hz) + 偶尔随机脉冲,模拟远处模糊日常
- 淡出: 尾段渐弱到 0

音量:对应 note.velocity/127 (velocity 已存 15~28,极淡 ppp 范围)
时长:duration 字段 (2分=半个全音符 ≈ 1.76s, 实际按 beat_pos 算到下个事件)

输出:workspace/project/走在/song_engineer/track/11_自然白噪音.wav
"""
import os
import json
import numpy as np
import soundfile as sf

# 路径
TD = os.path.join("workspace", "project", "走在", "song_engineer", "track")
JP = os.path.join(TD, "11_自然白噪音.json")
WP = os.path.join(TD, "11_自然白噪音.wav")

SR = 44100
BPM = 68
BEAT_SEC = 60.0 / BPM  # 0.8824s
BAR_SEC = BEAT_SEC * 4  # 3.529s
TOTAL_BARS = 52
TOTAL_SEC = BAR_SEC * TOTAL_BARS + 1.5  # 留 1.5s 尾音衰减


def pink_noise(n_samples):
    """粉噪生成(Paul Kellet 法,O(N)):白噪通过多个 IIR 级联滤波"""
    rng = np.random.default_rng(seed=42)
    white = rng.standard_normal(n_samples).astype(np.float32)
    # 7 个极点,每个贡献不同频段
    b = [0.049922035, -0.095993537, 0.050612699, -0.004408786,
         0.009919915, -0.002326762, 0.000453132]
    a_pink = [1.0, -2.494956002, 2.017265875, -0.522189400,
              -0.022641092, 0.049576596, 0.004277211, 0.001385356]
    out = np.zeros(n_samples, dtype=np.float32)
    for bi, ai in zip(b, a_pink):
        out += bi * white
    # 简化版:直接用一个低通粉噪近似(满足柔的听感即可)
    sig = np.cumsum(white)
    sig -= np.linspace(sig[0], sig[-1], n_samples)  # 去 DC 漂移
    sig = sig / (np.max(np.abs(sig)) + 1e-9) * 0.9
    return sig.astype(np.float32)


def lowpass(sig, cutoff_hz, sr=SR):
    """简易一阶 IIR 低通"""
    rc = 1.0 / (2 * np.pi * cutoff_hz)
    dt = 1.0 / sr
    alpha = dt / (rc + dt)
    out = np.zeros_like(sig)
    prev = 0.0
    for i, x in enumerate(sig):
        prev = prev + alpha * (x - prev)
        out[i] = prev
    return out


def bandpass(sig, low_hz, high_hz, sr=SR):
    """简易一阶带通: highpass + lowpass"""
    sig_hp = highpass(sig, low_hz, sr)
    sig_bp = lowpass(sig_hp, high_hz, sr)
    return sig_bp


def highpass(sig, cutoff_hz, sr=SR):
    """简易一阶 IIR 高通"""
    rc = 1.0 / (2 * np.pi * cutoff_hz)
    dt = 1.0 / sr
    alpha = rc / (rc + dt)
    out = np.zeros_like(sig)
    prev_x = 0.0
    prev_y = 0.0
    for i, x in enumerate(sig):
        prev_y = alpha * (prev_y + x - prev_x)
        prev_x = x
        out[i] = prev_y
    return out


def lfo_modulate(sig, lfo_hz, depth=0.5, sr=SR):
    """用 LFO 缓慢调制信号幅度,模拟风声起伏"""
    t = np.arange(len(sig)) / sr
    mod = 1.0 + depth * np.sin(2 * np.pi * lfo_hz * t)
    return sig * mod


def envelope(n_samples, fade_in_s=0.3, fade_out_s=0.5, sustain=1.0):
    """ADSR-lite:淡入 + sustain + 淡出"""
    env = np.ones(n_samples, dtype=np.float32) * sustain
    fin = int(fade_in_s * SR)
    fout = int(fade_out_s * SR)
    if fin > 0:
        env[:fin] = np.linspace(0, sustain, fin)
    if fout > 0 and fin + fout < n_samples:
        env[-fout:] = np.linspace(sustain, 0, fout)
    return env


def note_to_segment(technique, n_samples):
    """根据 technique 字段生成对应类型的环境音"""
    n = n_samples
    t_low = technique.lower()
    if "雨" in technique:
        # 粉噪 + 低通 8kHz,模拟细密雨滴
        sig = pink_noise(n)
        sig = lowpass(sig, 8000)
        sig = sig * 0.7
    elif "风" in technique:
        # 粉噪 + 带通 200~1500Hz + LFO 调制
        sig = pink_noise(n)
        sig = bandpass(sig, 200, 1500)
        sig = lfo_modulate(sig, lfo_hz=0.3, depth=0.4)  # 慢 LFO 模拟风声起伏
        sig = sig * 0.6
    elif "远处" in technique or "日常" in technique:
        # 远处模糊声:粉噪 + 重低通(600Hz) + 偶尔脉冲
        sig = pink_noise(n)
        sig = lowpass(sig, 600)
        # 偶尔随机脉冲模拟远处人/车
        rng = np.random.default_rng(seed=123)
        pulse_pos = rng.integers(0, n, size=n // SR // 2)  # 每 2s 一个
        for p in pulse_pos:
            if p < n - SR // 4:
                sig[p:p + SR // 4] += rng.standard_normal(SR // 4) * 0.15
        sig = sig * 0.5
    elif "淡出" in technique:
        # 尾段渐弱,沿用前一段的粉噪
        sig = pink_noise(n) * 0.3
    else:
        sig = pink_noise(n) * 0.3
    # 包络
    fin = 0.5 if "淡入" in technique else 0.2
    fout = 0.5 if "淡出" in technique else 0.3
    env = envelope(n, fade_in_s=fin, fade_out_s=fout, sustain=1.0)
    return sig * env


def beat_pos_to_sec(bp):
    """小节.拍.位 -> 秒"""
    parts = bp.split(".")
    bar = int(parts[0])
    beat = int(parts[1]) if len(parts) > 1 else 1
    frac = int(parts[2]) if len(parts) > 2 else 1
    sec = (bar - 1) * BAR_SEC + (beat - 1) * BEAT_SEC + (frac - 1) * (BEAT_SEC / 2)
    return sec


def dur_to_sec(dur):
    """2分 -> 半全音符 -> 2 beats; 实际按 beat 计"""
    m = {"16分": 0.25, "8分": 0.5, "4分": 1, "2分": 2, "全分": 4, "全延": 4}
    return m.get(dur, 1) * BEAT_SEC


def main():
    if not os.path.exists(JP):
        print(f"[错误] 找不到 {JP}")
        return
    data = json.load(open(JP, encoding="utf-8"))
    notes = data.get("notes", [])
    if not notes:
        print("[错误] 无 notes")
        return

    total_samples = int(TOTAL_SEC * SR)
    track = np.zeros(total_samples, dtype=np.float32)

    # 按 beat_pos 排序(确保顺序覆盖)
    notes_sorted = sorted(notes, key=lambda n: beat_pos_to_sec(n.get("beat_pos", "1.1.1")))

    for i, n in enumerate(notes_sorted):
        technique = n.get("technique", "")
        velocity = int(n.get("velocity", 20))
        # 起点
        start_sec = beat_pos_to_sec(n.get("beat_pos", "1.1.1"))
        dur_sec = dur_to_sec(n.get("duration", "2分"))
        # 终点:如果下一条更近,则截到下一条起点
        if i + 1 < len(notes_sorted):
            next_sec = beat_pos_to_sec(notes_sorted[i + 1].get("beat_pos", "1.1.1"))
            end_sec = min(start_sec + dur_sec, next_sec)
        else:
            end_sec = min(start_sec + dur_sec, TOTAL_SEC - 1.5)
        # 至少 0.3s
        if end_sec - start_sec < 0.3:
            end_sec = start_sec + 0.3

        n_samples = int((end_sec - start_sec) * SR)
        seg = note_to_segment(technique, n_samples)
        # 按 velocity (15~28 范围) 缩放 -> ppp 极淡
        amp = (velocity / 127.0) * 1.4  # 系数 1.4 让 ppp 听起来仍能感到氛围
        seg = seg * amp

        s = int(start_sec * SR)
        e = min(s + len(seg), total_samples)
        track[s:e] += seg[:e - s]
        print(f"  [{i+1}/{len(notes)}] {technique:<8} bar={n.get('beat_pos','')[:6]:<7} sec={start_sec:.1f}~{end_sec:.1f} vel={velocity} amp={amp:.3f}")

    # 整体峰值归一化(留 0.3 headroom)
    peak = np.max(np.abs(track))
    if peak > 0:
        track = track / peak * 0.7

    sf.write(WP, track, SR)
    print(f"\n[输出] {WP}")
    print(f"  时长: {len(track)/SR:.1f}s | 峰值: {peak:.3f} | 段数: {len(notes_sorted)}")


if __name__ == "__main__":
    main()