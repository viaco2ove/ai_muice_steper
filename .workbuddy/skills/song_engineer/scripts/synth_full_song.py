#!/usr/bin/env python3
"""
synth_full_song.py - 全曲合成:吉他+人声叠加输出 wav

读:
- 01_吉他.json(逐音符 beat,吉他轨)
- 02_主唱.json(melody_note_level 逐音符含 char/note/midi/beat_pos,人声轨)
用 numpy 极简合成两个轨,叠加输出 wav。

人声轨 char 字段携带逐字歌词,合成时把歌词写到 wav 的 metadata(可选)。

依赖:synthesize_midi.py 的 render_note + midi 解析逻辑(本脚本内联精简版,避免循环导入)。
"""

import argparse
import os
import sys
import json
import numpy as np
import soundfile as sf

SAMPLE_RATE = 22050
BPM = 68

# 时值 ticks(480 ticks/beat)
DUR2TICKS = {"16分": 120, "8分": 240, "4分": 480, "2分": 960,
             "全分": 480, "全延": 480, "": 240}

# 力度映射
DYN2VEL = {"ppp": 30, "pp": 45, "p": 60, "mp": 75,
            "mf": 85, "f": 95, "ff": 105, "fff": 115, "": 60}

NOTE2MIDI = {"C":0,"C#":1,"D":2,"D#":3,"E":4,"F":5,"F#":6,"G":7,"G#":8,"A":9,"A#":10,"B":11}


def note_to_midi(name: str) -> int | None:
    if not name or name.strip() in ("", "留白"): return None
    name = name.replace("泛音", "").strip()
    import re
    m = re.match(r"([A-G][#]?)(-?\d+)", name)
    if not m or m.group(1) not in NOTE2MIDI: return None
    return NOTE2MIDI[m.group(1)] + (int(m.group(2)) + 1) * 12


def midi_to_freq(m: int) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def vel_to_amp(v: int) -> float:
    return (v / 127.0) ** 1.5


def render_guitar(midi_num: int, vel: int, dur_sec: float, sr: int) -> np.ndarray:
    """钢弦吉他近似:基频+3谐波,渐变包络"""
    f = midi_to_freq(midi_num)
    amp = vel_to_amp(vel) * 0.3
    t = np.linspace(0, dur_sec, int(dur_sec * sr), endpoint=False)
    harmonics = [(1, 1.0), (2, 0.5), (3, 0.3), (4, 0.15)]
    wave = sum(w * np.sin(2 * np.pi * f * h * t) for h, w in harmonics)
    env = np.ones_like(t)
    attack = min(0.005, dur_sec * 0.3)
    a = int(attack * sr)
    env[:a] = np.linspace(0, 1, a)
    decay = 3.0 / dur_sec if dur_sec > 0.1 else 20
    env[a:] = np.exp(-decay * (t[a:] - attack))
    return wave * env * amp


def render_vocal(midi_num: int, vel: int, dur_sec: float, sr: int) -> np.ndarray:
    """人声近似:基频+共振峰(F1=800,F2=1200)+vibrato(5Hz)+气声(白噪)"""
    np.random.seed(midi_num)  # 同一音高每次气声相同(避免每次重新合成变样)
    f = midi_to_freq(midi_num)
    f1, f2 = 800, 1200
    amp = vel_to_amp(vel) * 0.35
    t = np.linspace(0, dur_sec, int(dur_sec * sr), endpoint=False)
    vibrato = 1.0 + 0.01 * np.sin(2 * np.pi * 5 * t)
    wave = (np.sin(2 * np.pi * f * vibrato * t)
            + 0.3 * np.sin(2 * np.pi * f1 * vibrato * t)
            + 0.2 * np.sin(2 * np.pi * f2 * vibrato * t))
    breath = np.random.randn(len(t)) * 0.04
    wave = wave + breath
    env = np.ones_like(t)
    attack = min(0.02, dur_sec * 0.3)
    a = int(attack * sr)
    env[:a] = np.linspace(0, 1, a)
    decay = 1.5 / dur_sec if dur_sec > 0.1 else 10
    env[a:] = np.exp(-decay * (t[a:] - attack))
    return wave * env * amp


def bar_offset(bar_idx: int, beat: int, frac: int) -> int:
    """小节.拍.位 -> 离曲首的 tick 数(480 ticks/beat)"""
    ticks_per_beat = 480
    bar_tick = (bar_idx - 1) * 4 * ticks_per_beat
    beat_tick = (beat - 1) * ticks_per_beat
    frac_offset = (frac - 1) * (ticks_per_beat // 2)
    return bar_tick + beat_tick + frac_offset


def render_guitar_track(json_path: str, sr: int, bpm: int) -> tuple[np.ndarray, list]:
    """渲染吉他轨:bars[].beats[]"""
    data = json.load(open(json_path, encoding="utf-8"))
    bars = data.get("bars", [])

    # 算总时长
    total_ticks = 0
    for i, bar in enumerate(bars):
        for b in bar.get("beats", []):
            pos = b.get("pos", "1.1").split(".")
            try:
                beat = int(pos[0]); frac = int(pos[1]) if len(pos) > 1 else 1
            except (ValueError, IndexError):
                continue
            dur_ticks = DUR2TICKS.get(b.get("dur", "4分"), 480)
            end_tick = bar_offset(i + 1, beat, frac) + dur_ticks
            total_ticks = max(total_ticks, end_tick)
    total_sec = total_ticks / 480 / bpm * 60
    out = np.zeros(int(total_sec * sr) + sr)

    lyrics = []  # 收集歌词行(吉他轨无歌词,留空)
    for i, bar in enumerate(bars):
        for b in bar.get("beats", []):
            note_name = b.get("actual") or b.get("note") or ""
            midi_num = note_to_midi(note_name)
            if midi_num is None: continue
            pos = b.get("pos", "1.1").split(".")
            try:
                beat = int(pos[0]); frac = int(pos[1]) if len(pos) > 1 else 1
            except (ValueError, IndexError):
                continue
            tick = bar_offset(i + 1, beat, frac)
            dur_ticks = DUR2TICKS.get(b.get("dur", "4分"), 480)
            dur_sec = dur_ticks / 480 / bpm * 60
            vel = DYN2VEL.get(b.get("dynamics", "p"), 60)
            if dur_sec > 0.01:
                start_sec = tick / 480 / bpm * 60
                sample_start = int(start_sec * sr)
                w = render_guitar(midi_num, vel, dur_sec, sr)
                end = min(sample_start + len(w), len(out))
                out[sample_start:end] += w[:end - sample_start]
    return out, lyrics


def render_vocal_track(json_path: str, sr: int, bpm: int) -> tuple[np.ndarray, list]:
    """渲染人声轨:melody_note_level.sections[].[]"""
    data = json.load(open(json_path, encoding="utf-8"))
    m = data.get("melody_note_level")
    if not m:
        return np.zeros(sr), []

    # 算总时长
    max_tick = 0
    notes_all = []
    for section_name, notes in m.get("sections", {}).items():
        for n in notes:
            midi_num = n.get("midi")
            if midi_num is None or midi_num < 0: continue
            bp = n.get("beat_pos", "1.1.1").split(".")
            try:
                bar = int(bp[0]); beat = int(bp[1]) if len(bp) > 1 else 1
                frac_str = bp[2] if len(bp) > 2 else "1"
                if frac_str == "末": beat = min(beat + 1, 4); frac = 1
                else: frac = int(frac_str)
            except (ValueError, IndexError): continue
            tick = bar_offset(bar, beat, frac)
            dur_str = n.get("duration", "8分")
            dur_ticks = DUR2TICKS.get(dur_str, 240)
            end_tick = tick + dur_ticks
            max_tick = max(max_tick, end_tick)
            notes_all.append((tick, midi_num, dur_ticks, n))
    total_sec = max_tick / 480 / bpm * 60
    out = np.zeros(int(total_sec * sr) + sr)

    lyrics = []
    for tick, midi_num, dur_ticks, n in notes_all:
        dur_sec = dur_ticks / 480 / bpm * 60
        vel = DYN2VEL.get(n.get("dynamics", "p"), 60)
        if dur_sec > 0.01:
            start_sec = tick / 480 / bpm * 60
            sample_start = int(start_sec * sr)
            w = render_vocal(midi_num, vel, dur_sec, sr)
            end = min(sample_start + len(w), len(out))
            out[sample_start:end] += w[:end - sample_start]
            char = n.get("char", "")
            if char and char not in ("…", "...", "*"):
                lyrics.append((start_sec, char))

    return out, lyrics


def main():
    ap = argparse.ArgumentParser(description="合成吉他+人声 wav")
    ap.add_argument("--guitar", default="workspace/project/走在/song_engineer/track/01_吉他.json",
                    help="吉他轨 JSON")
    ap.add_argument("--vocal", default="workspace/project/走在/song_engineer/track/02_主唱.json",
                    help="主唱轨 JSON")
    ap.add_argument("-o", "--output", default="workspace/project/走在/song_engineer/track/full_song.wav",
                    help="输出 wav")
    ap.add_argument("--bpm", type=int, default=BPM)
    ap.add_argument("--guitar-vol", type=float, default=0.8, help="吉他音量(0-1)")
    ap.add_argument("--vocal-vol", type=float, default=1.0, help="人声音量(0-1)")
    args = ap.parse_args()

    print(f"[渲染吉他] {args.guitar}")
    g, _ = render_guitar_track(args.guitar, SAMPLE_RATE, args.bpm)
    print(f"  时长: {len(g)/SAMPLE_RATE:.1f}秒")

    print(f"[渲染人声] {args.vocal}")
    v, lyrics = render_vocal_track(args.vocal, SAMPLE_RATE, args.bpm)
    print(f"  时长: {len(v)/SAMPLE_RATE:.1f}秒  含歌词字: {len(lyrics)}")

    # 对齐长度
    L = max(len(g), len(v))
    g = np.pad(g, (0, L - len(g)))
    v = np.pad(v, (0, L - len(v)))

    # 叠加(音量平衡)
    mix = g * args.guitar_vol + v * args.vocal_vol

    # 归一化防削波
    max_val = np.max(np.abs(mix))
    if max_val > 0.95:
        mix = mix / max_val * 0.95
        print(f"  [归一化] 原峰值 {max_val:.3f} -> 0.95")

    sf.write(args.output, mix.astype(np.float32), SAMPLE_RATE, subtype="PCM_16")
    print(f"[输出] {args.output}")
    print(f"  时长: {len(mix)/SAMPLE_RATE:.1f}秒 | 峰值: {max_val:.3f} | 采样率: {SAMPLE_RATE}")
    if lyrics[:20]:
        print(f"  歌词前20字(时间+字):")
        for t, c in lyrics[:20]:
            print(f"    {t:6.2f}s: {c}")


if __name__ == "__main__":
    main()