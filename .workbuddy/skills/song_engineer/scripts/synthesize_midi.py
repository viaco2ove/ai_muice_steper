#!/usr/bin/env python3
"""
synthesize_midi.py - 极简 MIDI 合成 wav

不依赖 FluidSynth/Timidity,用 numpy 直接生成:
- 吉他音:基频+多个谐波(钢弦吉他特征)
- 钢琴音:基频+前几个谐波,带衰减

每音按 velocity 控制振幅,按 MIDI 时长渲染。
输出 16-bit WAV,直接可播放。

仅供快速试听,非专业合成(替代 FluidSynth 用)。
"""

import sys
import numpy as np
import soundfile as sf
import mido
import argparse


SAMPLE_RATE = 22050  # 低采样率够用,文件小


def midi_to_freq(m: int) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def vel_to_amp(v: int) -> float:
    """velocity 0-127 -> 振幅 0-1"""
    return (v / 127.0) ** 1.5  # 1.5 次方让弱音更弱


def render_note(midi_num: int, vel: int, dur_sec: float,
                timbre: str = "guitar", sr: int = SAMPLE_RATE) -> np.ndarray:
    """
    渲染单个音符的音频波形。
    guitar: 钢弦吉他近似(基频+3个谐波,带渐变包络)
    piano: 钢琴近似(基频+4个谐波,attack快 decay慢)
    vocal: 人声近似(共振峰+vibrato+气声)
    """
    f = midi_to_freq(midi_num)
    amp = vel_to_amp(vel) * 0.3  # 总体音量压低防削波
    t = np.linspace(0, dur_sec, int(dur_sec * sr), endpoint=False)

    if timbre == "guitar":
        # 吉他:谐波 1,2,3,4(衰减),pluck attack,长decay
        harmonics = [(1, 1.0), (2, 0.5), (3, 0.3), (4, 0.15)]
        env = np.ones_like(t)
        attack = min(0.005, dur_sec * 0.3)
        attack_samples = int(attack * sr)
        env[:attack_samples] = np.linspace(0, 1, attack_samples)
        decay_rate = 3.0 / dur_sec if dur_sec > 0.1 else 20
        env[attack_samples:] = np.exp(-decay_rate * (t[attack_samples:] - attack))
    elif timbre == "piano":
        harmonics = [(1, 1.0), (2, 0.6), (3, 0.3), (4, 0.15), (5, 0.08)]
        env = np.ones_like(t)
        attack = min(0.003, dur_sec * 0.05)
        attack_samples = int(attack * sr)
        env[:attack_samples] = np.linspace(0, 1, attack_samples)
        decay_rate = 4.0 / dur_sec if dur_sec > 0.1 else 30
        env[attack_samples:] = np.exp(-decay_rate * (t[attack_samples:] - attack))
    elif timbre == "vocal":
        # 人声模拟:基频 + 共振峰(formant) + 轻微 vibrato + 弱气声
        # 元音"ah"的共振峰简化:F1=800Hz, F2=1200Hz
        f1, f2 = 800, 1200
        # vibrato 5Hz 频率微调
        vibrato = 1.0 + 0.01 * np.sin(2 * np.pi * 5 * t)
        wave = (1.0 * np.sin(2 * np.pi * f * vibrato * t)
                + 0.3 * np.sin(2 * np.pi * f1 * vibrato * t)
                + 0.2 * np.sin(2 * np.pi * f2 * vibrato * t))
        # 气声(白噪)
        breath = np.random.randn(len(t)) * 0.05
        wave = wave + breath
        # 包络:中等attack,长sustain(人声是连续)
        env = np.ones_like(t)
        attack = min(0.02, dur_sec * 0.3)
        attack_samples = int(attack * sr)
        env[:attack_samples] = np.linspace(0, 1, attack_samples)
        # sustain + 缓慢decay
        decay_rate = 1.5 / dur_sec if dur_sec > 0.1 else 10
        env[attack_samples:] = np.exp(-decay_rate * (t[attack_samples:] - attack))
    else:
        # 纯正弦
        harmonics = [(1, 1.0)]
        env = np.ones_like(t)

    if timbre != "vocal":
        wave = np.zeros_like(t)
        for h, w in harmonics:
            wave += w * np.sin(2 * np.pi * f * h * t)

    return wave * env * amp


def midi_to_wav(midi_path: str, wav_path: str, timbre: str = "guitar"):
    """
    读 MIDI,渲染成 wav。
    """
    mid = mido.MidiFile(midi_path)
    tpb = mid.ticks_per_beat
    cur_tempo = 500000
    # 合并所有 track 的事件,按 tick 排序
    all_events = []
    for track in mid.tracks:
        ct = 0
        for msg in track:
            ct += msg.time
            all_events.append((ct, msg))
    all_events.sort(key=lambda x: x[0])

    # 第一遍:计算总时长(精确处理多个 set_tempo)
    cur_tempo = 500000
    bpm = 60_000_000 / cur_tempo
    total_sec = 0
    prev_tick = 0
    for tick, msg in all_events:
        if msg.type == "set_tempo":
            total_sec += (tick - prev_tick) / tpb / bpm * 60
            prev_tick = tick
            cur_tempo = msg.tempo
            bpm = 60_000_000 / cur_tempo
    total_sec += (all_events[-1][0] - prev_tick) / tpb / bpm * 60

    sr = SAMPLE_RATE
    out = np.zeros(int(total_sec * sr) + sr)

    # 第二遍:渲染(同样精确处理多个 set_tempo)
    cur_tempo = 500000
    bpm = 60_000_000 / cur_tempo
    cur_time_sec = 0
    prev_tick = 0
    active = {}
    for tick, msg in all_events:
        # 时间累积(当前 tempo 段)
        cur_time_sec += (tick - prev_tick) / tpb / bpm * 60
        prev_tick = tick
        if msg.type == "set_tempo":
            cur_tempo = msg.tempo
            bpm = 60_000_000 / cur_tempo
            continue
        if msg.type == "note_on" and msg.velocity > 0:
            active[msg.note] = (cur_time_sec, msg.velocity)
        elif (msg.type == "note_off") or (msg.type == "note_on" and msg.velocity == 0):
            if msg.note in active:
                start_sec, vel = active.pop(msg.note)
                dur_sec = cur_time_sec - start_sec
                if dur_sec > 0.01:
                    sample_start = int(start_sec * sr)
                    note_wave = render_note(msg.note, vel, dur_sec, timbre, sr)
                    end = min(sample_start + len(note_wave), len(out))
                    if end > sample_start:
                        out[sample_start:end] += note_wave[:end - sample_start]

    # 归一化防削波
    max_val = np.max(np.abs(out))
    if max_val > 0.95:
        out = out / max_val * 0.95

    sf.write(wav_path, out.astype(np.float32), sr)
    print(f"[输出] {wav_path}")
    print(f"  采样率: {sr} | 时长: {len(out)/sr:.1f}秒 | 最大振幅: {max_val:.3f}")


def main():
    ap = argparse.ArgumentParser(description="MIDI 极简合成 wav(不依赖外部工具)")
    ap.add_argument("input", help="MIDI 文件")
    ap.add_argument("-o", "--output", help="输出 wav 路径(默认同目录同名 .wav)")
    ap.add_argument("--timbre", default="guitar", choices=["guitar","piano","vocal","sine"],
                    help="音色(默认 guitar;vocal=人声模拟带共振峰)")
    args = ap.parse_args()

    if not args.output:
        base = sys.argv[1].rsplit(".", 1)[0]
        args.output = base + ".wav"

    # 根据文件名选默认音色
    if args.timbre == "guitar" and "吉他" in args.input:
        args.timbre = "guitar"
    elif args.timbre == "guitar" and "主唱" in args.input:
        args.timbre = "piano"  # 主唱用钢琴近似

    midi_to_wav(args.input, args.output, args.timbre)


if __name__ == "__main__":
    main()