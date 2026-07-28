# -*- coding: utf-8 -*-
"""
synth_full_song_fs.py - 用 FluidSynth + SoundFont 合成吉他+人声全曲 wav

真实 SoundFont 采样,音质远超 numpy 极简合成。
吉他:Steel Guitar(program 25)/Nylon(24)
人声:用 program 0 钢琴 SF 中的"Voice Oohs"(program 85)或钢琴(0)代替(SF 无人声歌词合成)

从 .env 读 fluidsynth_path / soundfonts_path。
"""
import os
import sys
import argparse
import numpy as np
import soundfile as sf

# 读 .env
_env = {}
_cur = os.path.dirname(os.path.abspath(__file__))
for _ in range(5):
    _c = os.path.join(_cur, ".env")
    if os.path.exists(_c):
        with open(_c, encoding="utf-8") as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    _env[k] = v
        break
    _cur = os.path.dirname(_cur)
FS_PATH = _env.get("fluidsynth_path", "")
SF_DIR = _env.get("soundfonts_path", "")
os.environ["PATH"] = os.path.join(FS_PATH, "bin") + ";" + os.environ["PATH"]

import fluidsynth
import mido

SAMPLE_RATE = 44100
CHUNK_SEC = 0.05


def find_sf(preferred=None):
    if preferred and os.path.exists(os.path.join(SF_DIR, preferred)):
        return os.path.join(SF_DIR, preferred)
    if os.path.isdir(SF_DIR):
        for f in sorted(os.listdir(SF_DIR)):
            if "GeneralUser" in f and f.lower().endswith((".sf2", ".sf3")):
                return os.path.join(SF_DIR, f)
        sfs = [f for f in os.listdir(SF_DIR) if f.lower().endswith((".sf2", ".sf3"))]
        if sfs:
            return os.path.join(SF_DIR, sfs[0])
    return None


def render_track_midi(midi_path, sf_path, program, gain=0.8):
    """用 FluidSynth 渲染单个 MIDI 为 mono float32 数组"""
    mid = mido.MidiFile(midi_path)
    tpb = mid.ticks_per_beat

    fs = fluidsynth.Synth(samplerate=SAMPLE_RATE, gain=gain)
    sfid = fs.sfload(sf_path)
    if sfid < 0:
        raise RuntimeError(f"SF 加载失败: {sf_path}")
    fs.program_select(0, sfid, 0, program)

    # 合并事件
    all_events = []
    for track in mid.tracks:
        ct = 0
        for msg in track:
            ct += msg.time
            all_events.append((ct, msg))
    all_events.sort(key=lambda x: x[0])

    # 总时长
    max_tick = max(t[0] for t in all_events) if all_events else 0
    total_sec = 0
    cur_tempo = 500000
    prev_tick = 0
    for tick, msg in all_events:
        if msg.type == "set_tempo":
            total_sec += (tick - prev_tick) / tpb / (60_000_000 / cur_tempo) * 60
            prev_tick = tick
            cur_tempo = msg.tempo
    total_sec += (max_tick - prev_tick) / tpb / (60_000_000 / cur_tempo) * 60
    total_sec += 1.0

    # tick -> sec 查找表
    def tick_to_sec(target):
        s = 0; ct = 500000; pt = 0
        for tick, msg in all_events:
            if tick > target: break
            if msg.type == "set_tempo":
                s += (tick - pt) / tpb / (60_000_000 / ct) * 60
                pt = tick; ct = msg.tempo
        s += (target - pt) / tpb / (60_000_000 / ct) * 60
        return s

    chunk_samples = int(SAMPLE_RATE * CHUNK_SEC)
    audio = []
    cur_sec = 0
    ev_idx = 0
    while cur_sec < total_sec:
        chunk_end = cur_sec + CHUNK_SEC
        while ev_idx < len(all_events):
            tick, msg = all_events[ev_idx]
            if tick_to_sec(tick) > chunk_end:
                break
            if msg.type == "program_change":
                try: fs.program_select(msg.channel, sfid, 0, msg.program)
                except: pass
            elif msg.type == "note_on" and msg.velocity > 0:
                fs.noteon(msg.channel, msg.note, msg.velocity)
            elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                fs.noteoff(msg.channel, msg.note)
            elif msg.type == "control_change":
                fs.cc(msg.channel, msg.control, msg.value)
            ev_idx += 1
        samples = fs.get_samples(chunk_samples)
        audio.append(samples)
        cur_sec = chunk_end

    audio = np.concatenate(audio).astype(np.float32)
    if len(audio) % 2 == 0:
        audio = audio.reshape(-1, 2).mean(axis=1)
    fs.delete()
    return audio


def main():
    ap = argparse.ArgumentParser(description="FluidSynth 合成吉他+人声全曲")
    ap.add_argument("--guitar", default="workspace/project/走在/song_engineer/track/01_吉他.mid")
    ap.add_argument("--vocal", default="workspace/project/走在/song_engineer/track/02_主唱.mid")
    ap.add_argument("-o", "--output", default="workspace/project/走在/song_engineer/track/full_song_fs.wav")
    ap.add_argument("--guitar-program", type=int, default=25, help="吉他音色(25=钢弦吉他,24=尼龙)")
    ap.add_argument("--vocal-program", type=int, default=85, help="人声替代音色(85=Voice Oohs,0=钢琴,54=Synth Voice)")
    ap.add_argument("--guitar-vol", type=float, default=0.7)
    ap.add_argument("--vocal-vol", type=float, default=1.0)
    args = ap.parse_args()

    sf_path = find_sf()
    if not sf_path:
        print("[错误] 未找到 SoundFont"); sys.exit(1)

    print(f"[吉他] {args.guitar} (program={args.guitar_program})")
    g = render_track_midi(args.guitar, sf_path, args.guitar_program)
    print(f"  时长: {len(g)/SAMPLE_RATE:.1f}s")

    print(f"[人声] {args.vocal} (program={args.vocal_program})")
    v = render_track_midi(args.vocal, sf_path, args.vocal_program)
    print(f"  时长: {len(v)/SAMPLE_RATE:.1f}s")

    L = max(len(g), len(v))
    g = np.pad(g, (0, L - len(g)))
    v = np.pad(v, (0, L - len(v)))
    mix = g * args.guitar_vol + v * args.vocal_vol

    peak = np.max(np.abs(mix))
    if peak > 0.95:
        mix = mix / peak * 0.95
    sf.write(args.output, mix.astype(np.float32), SAMPLE_RATE)
    print(f"\n[输出] {args.output}")
    print(f"  时长: {len(mix)/SAMPLE_RATE:.1f}s | 峰值: {peak:.3f} | SF: {os.path.basename(sf_path)}")
    print(f"  吉他 vol={args.guitar_vol} program={args.guitar_program}")
    print(f"  人声 vol={args.vocal_vol} program={args.vocal_program}")


if __name__ == "__main__":
    main()