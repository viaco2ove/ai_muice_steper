#!/usr/bin/env python3
"""
export_track_to_midi.py - song_engineer 分轨 MIDI 导出

读 song_engineer/track/*.json 的逐音符级数据,导出为可播放的 MIDI 文件。

支持所有分轨(吉他/主唱/歌词,因格式统一),通过 --channel 区分:
- 吉他:钢琴音色通道,实际音高(已含Capo)
- 主唱:钢琴或清音通道,实际音高
- 歌词轨无 beat 数据(只有歌词行),会跳过 note 导出

处理:
- 音名 -> MIDI 编号
- 时值("4分"/"8分") -> ticks
- 位置(pos="1.1" = 第1拍第1位) -> 累计 tick
- 力度(dynamics pp/p/mp) -> velocity
- 特殊音名(泛音/留白) 跳过
"""

import argparse
import os
import sys
import json
import re

NOTE2MIDI = {"C":0,"C#":1,"D":2,"D#":3,"E":4,"F":5,"F#":6,"G":7,"G#":8,"A":9,"A#":10,"B":11}

DUR2TICKS = {
    "16分": 120,   # 480/4
    "8分": 240,    # 480/2
    "4分": 480,    # 480
    "2分": 960,    # 480*2
    "全分": 480,   # 占满小节(简化处理)
    "全延": 480,   # 占满
}

DYN2VEL = {
    "ppp": 30, "pp": 45, "p": 60, "mp": 75,
    "mf": 85, "f": 95, "ff": 105, "fff": 115,
}


def note_to_midi(name: str) -> int | None:
    """音名(如 'C3', 'Bb3', 'G#3泛音') 转 MIDI 编号。泛音视为同音高(忽略泛音标记)。"""
    if not name or name.strip() in ("", "留白"):
        return None
    # 去掉"泛音"标记
    name = name.replace("泛音", "").strip()
    # 支持 # 升号 和 b 降号
    m = re.match(r"([A-G])([#b]?)(-?\d+)", name)
    if not m:
        return None
    letter, accidental, octave = m.group(1), m.group(2), m.group(3)
    # 转换:先转音名+升降号到 pitch class
    base = {"C":0,"D":2,"E":4,"F":5,"G":7,"A":9,"B":11}[letter]
    if accidental == "#":
        base += 1
    elif accidental == "b":
        base -= 1
    return base + (int(octave) + 1) * 12


def pos_to_offset(pos: str) -> tuple[int, int]:
    """pos='1.1' -> (拍号=1, 拍内位=1); '2.2' -> (2,2); '4.1' -> (4,1)"""
    parts = pos.split(".")
    return int(parts[0]), int(parts[1]) if len(parts) > 1 else 1


def bar_offset(bar_idx: int, pos: tuple[int, int]) -> int:
    """
    算某个 bar 某个 pos 离曲首的 tick 数。
    bar_idx 从 1 开始(对应 bars[0])。
    每小节 4 拍 = 1920 ticks(480*4)。
    pos (拍号 1-4, 拍内位 1-2):1.1=0,1.2=240,2.1=480,2.2=720,3.1=960,3.2=1200,4.1=1440,4.2=1680
    """
    beats_per_bar = 4
    ticks_per_beat = 480
    bar_tick = (bar_idx - 1) * beats_per_bar * ticks_per_beat
    beat, frac = pos
    beat_start_tick = (beat - 1) * ticks_per_beat
    frac_offset = (frac - 1) * (ticks_per_beat // 2)
    return bar_tick + beat_start_tick + frac_offset


def export_track(json_path: str, output_path: str, tempo_bpm: int = 68, instrument_program: int = 0):
    """
    instrument_program: 0=钢琴,24=尼龙吉他,25=钢弦吉他,40=小提琴等
    支持两种数据源:
    - bars 字段(吉他逐小节 beat):bars[i].beats[j]
    - melody_note_level(主唱逐音符):sections['Verse 1'] 等
    """
    import mido
    data = json.load(open(json_path, encoding="utf-8"))
    # track_name 必须 ASCII (mido MetaMessage 用 latin-1),中文名做映射
    NAME_MAP = {"木吉他":"Acoustic Guitar","主唱":"Vocal","歌词":"Lyrics","鼓组":"Drums"}
    raw_name = data.get("name", data.get("track_id", "track"))
    track_name = NAME_MAP.get(raw_name, raw_name)
    try:
        track_name.encode("ascii")
    except UnicodeEncodeError:
        track_name = f"track_{data.get('track_id','?')}"

    mid = mido.MidiFile()
    mid.ticks_per_beat = 480
    tr = mido.MidiTrack()
    mid.tracks.append(tr)
    tr.append(mido.MetaMessage("track_name", name=track_name, time=0))
    tr.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(tempo_bpm), time=0))
    tr.append(mido.Message("program_change", program=instrument_program, time=0))

    events = []  # (tick, midi, dur_tick, vel, label)

    # 源1:bars (吉他逐小节)
    bars = data.get("bars", [])
    for i, bar in enumerate(bars):
        beats = bar.get("beats", [])
        chord = bar.get("chord", "")
        for b in beats:
            note_name = b.get("actual") or b.get("note") or ""
            midi_num = note_to_midi(note_name)
            if midi_num is None:
                continue
            pos = pos_to_offset(b["pos"])
            tick = bar_offset(i + 1, pos)
            dur = DUR2TICKS.get(b.get("dur", "4分"), 480)
            vel = DYN2VEL.get(b.get("dynamics", "p"), 60)
            events.append((tick, midi_num, dur, vel, chord))

    # 源2:melody_note_level (主唱逐音符,beat_pos 形如 "5.1.1")
    m = data.get("melody_note_level")
    if m:
        # 用 sections_detail 的 bars 区间(更精确)或总小节数
        sections_detail = data.get("sections_detail", [])
        section_bars = {s.get("bars",""): s for s in sections_detail}
        for section_name, notes in m.get("sections", {}).items():
            for n in notes:
                midi_num = n.get("midi")
                if midi_num is None or midi_num < 0:
                    continue
                bp = n.get("beat_pos", "1.1.1")
                # beat_pos 形如 "5.1.1"(bar.beat.frac) 或 "52.4末"(bar.beat.末)
                parts = bp.split(".")
                try:
                    bar_num = int(parts[0])
                    beat = int(parts[1]) if len(parts) > 1 else 1
                    frac_str = parts[2] if len(parts) > 2 else "1"
                    # "末" 表示该小节最末位置(beat+1 第1位前)
                    if frac_str == "末":
                        beat = min(beat + 1, 4)  # 推进到下一拍
                        frac = 1
                    else:
                        frac = int(frac_str)
                    tick = bar_offset(bar_num, (beat, frac))
                except (ValueError, IndexError):
                    continue
                # duration "8分"="0.5拍" -> 240 ticks
                dur_str = n.get("duration", "8分")
                dur = DUR2TICKS.get(dur_str, 240)
                vel = DYN2VEL.get(n.get("dynamics", "p"), 60)
                events.append((tick, midi_num, dur, vel, section_name))

    # 源3:notes 扁平结构(吉他/环境音轨,每音含 note/duration/beat_pos/velocity)
    flat_notes = data.get("notes", [])
    for n in flat_notes:
        if not isinstance(n, dict):
            continue  # 跳过非音符(如备注字符串)
        note_name = n.get("actual") or n.get("note") or ""
        # slap/noise 等无音高打击:midi=0,用 channel 9(鼓)或跳过
        if note_name in ("slap", "noise") or n.get("midi", -1) == 0:
            continue  # 无音高打击暂跳过(SF 鼓轨需专门处理)
        midi_num = note_to_midi(note_name)
        if midi_num is None:
            continue
        bp = n.get("beat_pos", "1.1.1").split(".")
        try:
            bar_num = int(bp[0])
            beat = int(bp[1]) if len(bp) > 1 else 1
            frac_str = bp[2] if len(bp) > 2 else "1"
            if frac_str == "末":
                beat = min(beat + 1, 4); frac = 1
            else:
                frac = int(frac_str)
        except (ValueError, IndexError):
            continue
        tick = bar_offset(bar_num, (beat, frac))
        dur = DUR2TICKS.get(n.get("duration", "4分"), 480)
        vel = n.get("velocity", 60)
        if isinstance(vel, str):
            vel = DYN2VEL.get(vel, 60)
        events.append((tick, midi_num, dur, int(vel), n.get("chord", "")))

    events.sort(key=lambda x: x[0])
    last_tick = 0
    for tick, midi_num, dur, vel, label in events:
        delta = max(0, tick - last_tick)
        tr.append(mido.Message("note_on", note=midi_num, velocity=vel, time=delta))
        tr.append(mido.Message("note_off", note=midi_num, velocity=0, time=dur))
        last_tick = tick + dur

    mid.save(output_path)
    print(f"[输出] {output_path}")
    print(f"  音轨: {track_name} | 音色 program={instrument_program} | BPM={tempo_bpm}")
    print(f"  音符数: {len(events)} (bars源:{sum(len(b.get('beats',[])) for b in bars) if bars else 0}, melody源:{sum(len(v) for v in m.get('sections',{}).values()) if m else 0}, notes源:{len(flat_notes)})")


def main():
    ap = argparse.ArgumentParser(description="song_engineer 分轨 MIDI 导出")
    ap.add_argument("input", help="输入 JSON(如 song_engineer/track/01_吉他.json)")
    ap.add_argument("-o", "--output", help="输出 MIDI 路径(默认同目录同名 .mid)")
    ap.add_argument("--bpm", type=int, default=68, help="BPM(默认68=走在的BPM)")
    ap.add_argument("--program", type=int, default=0, help="MIDI 音色 program(0=钢琴,25=钢弦吉他)")
    args = ap.parse_args()

    if not args.output:
        base = os.path.splitext(args.input)[0]
        args.output = base + ".mid"

    # 吉他默认用钢弦吉他音色,主唱用钢琴
    name = os.path.basename(args.input)
    if "吉他" in name and args.program == 0:
        args.program = 25  # 钢弦吉他

    os.makedirs(os.path.dirname(os.path.abspath(args.output)) or ".", exist_ok=True)
    export_track(args.input, args.output, args.bpm, args.program)


if __name__ == "__main__":
    main()