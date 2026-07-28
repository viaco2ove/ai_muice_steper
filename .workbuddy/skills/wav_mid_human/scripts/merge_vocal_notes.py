#!/usr/bin/env python3
"""
merge_vocal_notes.py - basic_pitch 人声 MIDI 连贯性后处理

针对 basic_pitch 把人声长音"抖碎成幻音"的问题做合并,逼近 Melodyne 的连贯感。
基于 vocals.csv vs melody_basicpitch.csv 的差异分析,三条规则:

1. 同音碎片合并:相邻音符音高相同/相近(±merge_tol半音)+ 间隙<gap_max -> 合并
2. 起音误判修正:长音被切成"邻音+正音",前碎音短<short_max且紧贴 -> 合并到后音(取后音音高)
3. 渐弱尾音保留:vel<tail_vel_th 的尾音不参与合并(Melodyne 精华,保留)

输入:basic_pitch 产出的 MIDI 或 CSV
输出:合并后的 MIDI + CSV
"""

import argparse
import os
import sys
import csv

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def midi_to_note(m: int) -> str:
    return f"{NOTE_NAMES[m % 12]}{(m // 12) - 1}"


def load_notes_from_csv(path: str) -> list[dict]:
    notes = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            notes.append({
                "start": float(r["start"]), "end": float(r["end"]),
                "duration": float(r["duration"]), "midi": int(r["midi"]),
                "velocity": int(r["velocity"]) if "velocity" in r and r["velocity"] else 80,
            })
    notes.sort(key=lambda x: x["start"])
    return notes


def load_notes_from_midi(path: str) -> list[dict]:
    import mido
    mid = mido.MidiFile(path); tpb = mid.ticks_per_beat
    allm = []
    for tr in mid.tracks:
        ct = 0
        for msg in tr:
            ct += msg.time; allm.append((ct, msg))
    allm.sort(key=lambda x: x[0])
    cur_t = 500000; active = {}; notes = []
    for ct, msg in allm:
        if msg.type == "set_tempo": cur_t = msg.tempo
        elif msg.type == "note_on" and msg.velocity > 0: active[msg.note] = (ct, cur_t, msg.velocity)
        elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
            if msg.note in active:
                st, st_t, vel = active.pop(msg.note)
                tps = tpb * 1000000 / st_t
                notes.append({"start": st/tps, "end": ct/tps, "duration": (ct-st)/tps, "midi": msg.note, "velocity": vel})
    notes.sort(key=lambda x: x["start"])
    return notes


def merge_notes(notes, merge_tol=0, gap_max=0.10, vel_tol=20, short_max=0.20, tail_vel_th=40):
    """
    合并规则(基于 Melodyne 切分边界的逆向分析):

    Melodyne 切分边界 = 音高变 | vel大变(>15) | 停顿(>0.1s)
    逆向:basic_pitch 应合并满足 ALL 以下的相邻音:
      - 音高相同(midi相等,merge_tol=0)  -- 音高变了就是新音,不合并
      - vel 差<vel_tol  -- 力度突变是新音的标志(Melodyne靠这个切渐弱尾音)
      - 间隙<gap_max  -- 停顿是新乐句

    这样能修正basic_pitch"音高不变却乱切"的问题,同时保留音高转折/力度转折/停顿。
    tail_vel_th: vel<此值视为渐弱尾音,不合并(保留)。
    """
    if not notes:
        return []

    # 第一遍:合并"同音+vel相近+小间隙"的相邻碎片
    merged = [dict(notes[0])]
    for cur in notes[1:]:
        prev = merged[-1]
        gap = cur["start"] - prev["end"]
        # 渐弱尾音独立保留
        if cur["velocity"] < tail_vel_th:
            merged.append(dict(cur)); continue
        # 同音 + vel相近 + 小间隙 -> 合并(修正basic_pitch同音乱切)
        if (cur["midi"] == prev["midi"]
                and abs(cur["velocity"] - prev["velocity"]) < vel_tol
                and gap <= gap_max):
            prev["end"] = max(prev["end"], cur["end"])
            prev["duration"] = prev["end"] - prev["start"]
            prev["velocity"] = max(prev["velocity"], cur["velocity"])
        else:
            merged.append(dict(cur))

    # 第二遍:起音误判修正--短碎音紧贴后音+音高相邻1-3半音,并入后音(用后音音高)
    final = [dict(merged[0])] if merged else []
    for cur in merged[1:]:
        prev = final[-1]
        gap = cur["start"] - prev["end"]
        if (prev["duration"] < short_max and gap <= 0.03
                and 1 <= abs(cur["midi"] - prev["midi"]) <= 3
                and cur["velocity"] >= tail_vel_th):
            cur = dict(cur)
            cur["start"] = prev["start"]
            cur["duration"] = cur["end"] - cur["start"]
            final[-1] = cur
        else:
            final.append(dict(cur))

    return final


def export_csv(notes, path):
    for n in notes: n["note"] = midi_to_note(n["midi"])
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["start", "end", "duration", "note", "midi", "velocity"])
        w.writeheader()
        for n in notes:
            w.writerow({k: (round(n[k], 3) if isinstance(n[k], float) and k in ("start","end","duration") else n[k])
                        for k in ["start","end","duration","note","midi","velocity"]})


def export_midi(notes, path, tempo=120):
    import mido
    mid = mido.MidiFile(); mid.ticks_per_beat = 480
    tr = mido.MidiTrack(); mid.tracks.append(tr)
    tr.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(tempo), time=0))
    tr.append(mido.Message("program_change", program=0, time=0))
    tps = mid.ticks_per_beat * tempo / 60
    last_end = 0
    for n in notes:
        s = int(n["start"] * tps); e = int(n["end"] * tps)
        tr.append(mido.Message("note_on", note=n["midi"], velocity=n["velocity"], time=max(0, s-last_end)))
        tr.append(mido.Message("note_off", note=n["midi"], velocity=0, time=e-s))
        last_end = e
    mid.save(path)


def main():
    ap = argparse.ArgumentParser(description="basic_pitch 人声 MIDI 连贯性后处理(合并幻音)")
    ap.add_argument("input", help="输入 basic_pitch 的 MIDI 或 CSV")
    ap.add_argument("-o", "--output", default=".", help="输出目录")
    ap.add_argument("--merge-tol", type=int, default=0, help="同音合并容差半音(默认0=严格同音才合并)")
    ap.add_argument("--gap-max", type=float, default=0.10, help="合并最大间隙秒(默认0.10)")
    ap.add_argument("--vel-tol", type=int, default=20, help="vel差小于此值才合并(默认20)")
    ap.add_argument("--short-max", type=float, default=0.20, help="起音误判碎音最大时长秒(默认0.20)")
    ap.add_argument("--tail-vel", type=int, default=40, help="渐弱尾音vel阈值,低于不合并(默认40)")
    args = ap.parse_args()

    os.makedirs(args.output, exist_ok=True)

    if args.input.lower().endswith(".csv"):
        notes = load_notes_from_csv(args.input)
    else:
        notes = load_notes_from_midi(args.input)

    before = len(notes)
    print(f"[输入] {before} 个音符")

    merged = merge_notes(notes,
                         merge_tol=args.merge_tol,
                         gap_max=args.gap_max,
                         vel_tol=args.vel_tol,
                         short_max=args.short_max,
                         tail_vel_th=args.tail_vel)
    after = len(merged)
    print(f"[合并] {before} -> {after} 个音符 (减少 {before-after})")

    # 统计
    durs = [n["duration"] for n in merged]
    midis = [n["midi"] for n in merged]
    gaps = [merged[i+1]["start"] - merged[i]["end"] for i in range(len(merged)-1)]
    avg_gap = sum(gaps)/len(gaps) if gaps else 0
    print(f"  平均时长: {sum(durs)/len(durs):.3f}s | 平均间隙: {avg_gap:.3f}s")
    print(f"  音域: {midi_to_note(min(midis))}~{midi_to_note(max(midis))}")
    tail_count = sum(1 for n in merged if n["velocity"] < args.tail_vel)
    print(f"  渐弱尾音(保留): {tail_count} 个")

    export_csv(merged, os.path.join(args.output, "melody_merged.csv"))
    export_midi(merged, os.path.join(args.output, "melody_merged.mid"))
    print(f"[输出] {args.output}/melody_merged.mid + .csv")


if __name__ == "__main__":
    main()