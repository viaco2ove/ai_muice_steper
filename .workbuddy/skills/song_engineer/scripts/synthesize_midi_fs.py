# -*- coding: utf-8 -*-
"""
synthesize_midi_fs.py - 用 FluidSynth + SoundFont 把 MIDI 合成真实音质 wav

替代 numpy 极简合成,音质接近真实乐器(SoundFont 采样)。
从 .env 读 fluidsynth_path 和 soundfonts_path。

用法:
  python synthesize_midi_fs.py input.mid -o output.wav [--sf "GeneralUser GS v1.471.sf2"]
"""
import os
import sys
import argparse
import numpy as np
import soundfile as sf

# 读 .env(从项目根目录找,向上遍历)
_env = {}
_cur = os.path.dirname(os.path.abspath(__file__))
_env_path = None
for _ in range(5):
    _candidate = os.path.join(_cur, ".env")
    if os.path.exists(_candidate):
        _env_path = _candidate
        break
    _cur = os.path.dirname(_cur)
if not _env_path:
    _env_path = ".env"
with open(_env_path, encoding="utf-8") as f:
    for line in f:
        if "=" in line:
            k, v = line.strip().split("=", 1)
            _env[k] = v
FS_PATH = _env.get("fluidsynth_path", "")
SF_DIR = _env.get("soundfonts_path", "")
os.environ["PATH"] = os.path.join(FS_PATH, "bin") + ";" + os.environ["PATH"]

import fluidsynth
import mido

SAMPLE_RATE = 44100
CHUNK_SEC = 0.05  # 50ms 一块渲染


def list_soundfonts():
    """列出可用 SoundFont"""
    sfs = []
    if os.path.isdir(SF_DIR):
        for f in sorted(os.listdir(SF_DIR)):
            if f.lower().endswith((".sf2", ".sf3")):
                sfs.append(f)
    return sfs


def find_sf(preferred=None):
    if preferred:
        p = os.path.join(SF_DIR, preferred)
        if os.path.exists(p):
            return p
    # 默认优先 GeneralUser GS(轻量好用)
    for f in list_soundfonts():
        if "GeneralUser" in f:
            return os.path.join(SF_DIR, f)
    sfs = list_soundfonts()
    if sfs:
        return os.path.join(SF_DIR, sfs[0])
    return None


def synth_midi(midi_path, output_path, sf_path, gain=0.8):
    """用 FluidSynth 合成 MIDI -> wav"""
    mid = mido.MidiFile(midi_path)
    tpb = mid.ticks_per_beat

    fs = fluidsynth.Synth(samplerate=SAMPLE_RATE, gain=gain)
    sfid = fs.sfload(sf_path)
    if sfid < 0:
        raise RuntimeError(f"SoundFont 加载失败: {sf_path}")

    # 合并所有 track 的事件,按 tick 排序
    all_events = []
    for track in mid.tracks:
        ct = 0
        for msg in track:
            ct += msg.time
            all_events.append((ct, msg))
    all_events.sort(key=lambda x: x[0])

    # 找总时长(最后一个 note_off 或事件)
    cur_tempo = 500000
    bpm = 60_000_000 / cur_tempo
    max_tick = max(t[0] for t in all_events) if all_events else 0
    total_sec = 0
    prev_tick = 0
    for tick, msg in all_events:
        if msg.type == "set_tempo":
            total_sec += (tick - prev_tick) / tpb / bpm * 60
            prev_tick = tick
            cur_tempo = msg.tempo
            bpm = 60_000_000 / cur_tempo
    total_sec += (max_tick - prev_tick) / tpb / bpm * 60
    total_sec += 1.0  # 尾音收尾

    print(f"  SF: {os.path.basename(sf_path)} | sfid={sfid}")
    print(f"  总时长: {total_sec:.1f}s | 事件数: {len(all_events)}")

    # 渲染:按时间推进,在事件 tick 对应的时间点 noteon/noteoff
    chunk_samples = int(SAMPLE_RATE * CHUNK_SEC)
    audio = []
    cur_sec = 0
    cur_tempo = 500000
    bpm = 60_000_000 / cur_tempo
    prev_tick = 0
    ev_idx = 0

    while cur_sec < total_sec:
        # 推进到当前 chunk 结束时间,处理该时间段内的事件
        chunk_end_sec = cur_sec + CHUNK_SEC
        # 处理所有 tick <= 当前秒的事件
        while ev_idx < len(all_events):
            tick, msg = all_events[ev_idx]
            # 算这个 tick 的绝对秒数
            ev_sec = 0
            t_tempo = 500000
            t_bpm = 120
            t_prev = 0
            # 简化:用当前 bpm 累加(精确处理多 tempo)
            # 实际上我们边走边更新
            ev_tick_sec = _tick_to_sec(tick, all_events, tpb)
            if ev_tick_sec > chunk_end_sec:
                break
            _handle_event(fs, sfid, msg)
            ev_idx += 1

        samples = fs.get_samples(chunk_samples)
        audio.append(samples)
        cur_sec = chunk_end_sec

    audio = np.concatenate(audio)
    # get_samples 返回 int16 交错立体声
    audio = audio.astype(np.float32)
    if len(audio) % 2 == 0:
        audio = audio.reshape(-1, 2).mean(axis=1)  # 降混单声道

    # 归一化
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak * 0.9

    sf.write(output_path, audio.astype(np.float32), SAMPLE_RATE)
    print(f"  [输出] {output_path}")
    print(f"  时长: {len(audio)/SAMPLE_RATE:.1f}s | 峰值: {peak:.1f} | 采样率: {SAMPLE_RATE}")
    fs.delete()


def _tick_to_sec(target_tick, all_events, tpb):
    """算某 tick 的绝对秒数(处理多 tempo)"""
    cur_tempo = 500000
    prev_tick = 0
    sec = 0
    for tick, msg in all_events:
        if tick > target_tick:
            break
        if msg.type == "set_tempo":
            sec += (tick - prev_tick) / tpb / (60_000_000 / cur_tempo) * 60
            prev_tick = tick
            cur_tempo = msg.tempo
    sec += (target_tick - prev_tick) / tpb / (60_000_000 / cur_tempo) * 60
    return sec


def _handle_event(fs, sfid, msg):
    """把 MIDI 事件喂给 FluidSynth"""
    if msg.type == "set_tempo":
        # FluidSynth 自动处理 tempo(我们只喂 note 事件)
        pass
    elif msg.type == "program_change":
        # 选音色:program_change(channel, sfid, bank, preset)
        # 默认 bank=0, preset=msg.program
        try:
            fs.program_select(msg.channel, sfid, 0, msg.program)
        except Exception:
            pass
    elif msg.type == "note_on" and msg.velocity > 0:
        fs.noteon(msg.channel, msg.note, msg.velocity)
    elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
        fs.noteoff(msg.channel, msg.note)
    elif msg.type == "control_change":
        fs.cc(msg.channel, msg.control, msg.value)


def main():
    ap = argparse.ArgumentParser(description="FluidSynth 真实合成 MIDI->wav")
    ap.add_argument("input", help="MIDI 文件")
    ap.add_argument("-o", "--output", help="输出 wav")
    ap.add_argument("--sf", default=None, help="指定 SoundFont 文件名(在 sfs 目录)")
    ap.add_argument("--gain", type=float, default=0.8)
    args = ap.parse_args()

    if not args.output:
        args.output = args.input.rsplit(".", 1)[0] + "_fs.wav"

    sf_path = find_sf(args.sf)
    if not sf_path:
        print("[错误] 未找到 SoundFont,请检查 .env 的 soundfonts_path")
        sys.exit(1)

    print(f"[合成] {args.input}")
    synth_midi(args.input, args.output, sf_path, args.gain)


if __name__ == "__main__":
    main()