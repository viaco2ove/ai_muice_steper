#!/usr/bin/env python3
"""
compare_quality.py - 对比新旧 MIDI 质量

读取两个 MIDI 文件，统计碎音率/音域/音符数/平均时长等指标，
生成 quality_report.md 量化改进。
"""

import argparse
import os
import sys
import warnings

warnings.filterwarnings("ignore")

try:
    import mido
except ImportError:
    print("[错误] 缺少 mido", file=sys.stderr)
    sys.exit(1)

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def midi_to_note(m: int) -> str:
    return f"{NOTE_NAMES[m % 12]}{(m // 12) - 1}"


def parse_midi_notes(path: str) -> list[dict]:
    """解析 MIDI，返回 [{midi, duration_sec}] 列表。
    正确处理:合并所有track、velocity=0当note_off、读取真实tempo。"""
    mid = mido.MidiFile(path)
    tpb = mid.ticks_per_beat
    # 合并所有track为单一时间线
    all_msgs = []
    for track in mid.tracks:
        cur_tick = 0
        for msg in track:
            cur_tick += msg.time
            all_msgs.append((cur_tick, msg))
    all_msgs.sort(key=lambda x: x[0])
    cur_tempo = 500000  # 默认 120 BPM
    active = {}
    notes = []
    for cur_tick, msg in all_msgs:
        if msg.type == "set_tempo":
            cur_tempo = msg.tempo
        elif msg.type == "note_on" and msg.velocity > 0:
            active[msg.note] = (cur_tick, cur_tempo)
        elif (msg.type == "note_off") or (msg.type == "note_on" and msg.velocity == 0):
            if msg.note in active:
                start_tick, start_tempo = active.pop(msg.note)
                tps = tpb * 1_000_000 / start_tempo
                dur = (cur_tick - start_tick) / tps
                notes.append({"midi": msg.note, "duration": dur})
    return notes


def stats(notes: list[dict]) -> dict:
    if not notes:
        return {"count": 0}
    durs = [n["duration"] for n in notes]
    midis = [n["midi"] for n in notes]
    short = sum(1 for d in durs if d < 0.05)
    return {
        "count": len(notes),
        "short_count": short,
        "short_rate": short / len(notes) * 100,
        "min_dur": min(durs),
        "max_dur": max(durs),
        "avg_dur": sum(durs) / len(durs),
        "min_note": midi_to_note(min(midis)),
        "min_midi": min(midis),
        "max_note": midi_to_note(max(midis)),
        "max_midi": max(midis),
    }


def main():
    ap = argparse.ArgumentParser(description="对比新旧 MIDI 质量")
    ap.add_argument("old", help="旧 MIDI 文件")
    ap.add_argument("new", help="新 MIDI 文件")
    ap.add_argument("-o", "--output", default="quality_report.md", help="输出报告路径")
    args = ap.parse_args()

    old_notes = parse_midi_notes(args.old)
    new_notes = parse_midi_notes(args.new)
    old_s = stats(old_notes)
    new_s = stats(new_notes)

    def fmt_change(old_v, new_v, better="up", fmt="{:.1f}"):
        if old_v is None or new_v is None:
            return "-"
        delta = new_v - old_v
        sign = "+" if delta >= 0 else ""
        arrow = "↑" if (delta > 0) == (better == "up") and delta != 0 else ("↓" if delta != 0 else "=")
        return f"{fmt.format(new_v)} ({sign}{fmt.format(delta)} {arrow})"

    lines = []
    lines.append("# 人声 MIDI 质量对比报告\n")
    lines.append(f"- 旧版: `{args.old}`")
    lines.append(f"- 新版: `{args.new}`\n")

    lines.append("## 核心指标对比\n")
    lines.append("| 指标 | 旧版（recognize_melody.py） | 新版（wav_to_midi.py） | 评价 |")
    lines.append("|------|---------------------------|----------------------|------|")
    lines.append(f"| 音符总数 | {old_s['count']} | {new_s['count']} | {'✅ 大幅减少碎音' if new_s['count'] < old_s['count'] * 0.5 else '⚠️ 变化不大'} |")
    lines.append(f"| 碎音率(<50ms) | {old_s['short_rate']:.1f}% | {new_s['short_rate']:.1f}% | {'✅ 显著改善' if new_s['short_rate'] < old_s['short_rate'] * 0.3 else '⚠️'} |")
    lines.append(f"| 平均音符时长 | {old_s['avg_dur']:.3f}s | {new_s['avg_dur']:.3f}s | {'✅ 可听旋律线' if new_s['avg_dur'] > 0.2 else '⚠️ 仍偏碎'} |")
    lines.append(f"| 最短音符 | {old_s['min_dur']:.3f}s | {new_s['min_dur']:.3f}s | - |")
    lines.append(f"| 最长音符 | {old_s['max_dur']:.3f}s | {new_s['max_dur']:.3f}s | - |")
    lines.append(f"| 音域 | {old_s['min_note']}~{old_s['max_note']} (MIDI {old_s['min_midi']}-{old_s['max_midi']}) | {new_s['min_note']}~{new_s['max_note']} (MIDI {new_s['min_midi']}-{new_s['max_midi']}) | - |")

    lines.append("\n## 结论\n")
    improvement = old_s["short_rate"] - new_s["short_rate"]
    if new_s["short_rate"] < 15 and new_s["avg_dur"] > 0.2:
        lines.append(f"✅ **新版 MIDI 可听出旋律线**：碎音率从 {old_s['short_rate']:.1f}% 降至 {new_s['short_rate']:.1f}%（降低 {improvement:.1f} 个百分点），平均音符时长 {new_s['avg_dur']:.3f}s 达到可唱级别。")
    elif new_s["short_rate"] < old_s["short_rate"] * 0.5:
        lines.append(f"🟡 新版有改善（碎音率 {old_s['short_rate']:.1f}% -> {new_s['short_rate']:.1f}%），但仍可进一步调参优化。")
    else:
        lines.append(f"⚠️ 改善不明显，建议检查输入素材质量或调整清洗参数。")

    lines.append("\n## 改进原理")
    lines.append("旧版 `recognize_melody.py` 用 pyin 逐帧提取仅做相邻同音合并，缺：最小音符时长过滤、中值滤波、跳变修正、音域过滤。")
    lines.append("新版 `wav_to_midi.py` 增加 8 步清洗管线（详见 references/wav_to_mid_principles.md）。\n")

    report = "\n".join(lines)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"[输出] {args.output}")
    print(f"  旧版: {old_s['count']}音符, 碎音率{old_s['short_rate']:.1f}%, 平均{old_s['avg_dur']:.3f}s")
    print(f"  新版: {new_s['count']}音符, 碎音率{new_s['short_rate']:.1f}%, 平均{new_s['avg_dur']:.3f}s")


if __name__ == "__main__":
    main()