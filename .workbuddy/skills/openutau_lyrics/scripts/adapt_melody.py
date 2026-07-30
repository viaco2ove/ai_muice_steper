#!/usr/bin/env python3
"""
adapt_melody.py — AI 旋律 MIDI 转调 + 时长适配
从 audio_chord_recognizer 的 vocals.ai.mid 转换到目标歌曲的调/节奏/TPB
"""
import argparse, os, sys, mido

def main():
    p = argparse.ArgumentParser(description="AI旋律 MIDI 转调+时长适配")
    p.add_argument('--project',   required=True,  help='歌曲名')
    p.add_argument('--tpb',       type=int, default=480, help='输出 TPB (默认480)')
    p.add_argument('--bpm',       type=int, default=68,  help='输出 BPM (默认68)')
    p.add_argument('--transpose', type=int, default=3,   help='转调半音数 C→Eb=3 (默认3)')
    p.add_argument('--bars',     type=int, default=52,  help='目标小节数 (默认52)')
    p.add_argument('--output',    help='直接指定输出 midi 路径 (覆盖推导)')
    args = p.parse_args()

    PROJ  = args.project
    TPB   = args.tpb
    BPM   = args.bpm
    TRANS = args.transpose

    ROOT  = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))))  # 项目根目录

    AI_MIDI  = os.path.join(ROOT, 'workspace', 'audio_output', PROJ,
                             'melody', 'vocals.ai.mid')
    OUT_DIR  = os.path.join(ROOT, 'workspace', 'project', PROJ,
                             'song_engineer', 'ai-track')
    OUT_MIDI = args.output or os.path.join(OUT_DIR, '02_主唱.mid')

    if not os.path.exists(AI_MIDI):
        print(f"[错误] 找不到 AI MIDI: {AI_MIDI}", file=sys.stderr)
        print("  请先运行 audio_chord_recognizer 识别旋律", file=sys.stderr)
        sys.exit(1)

    NAMES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']

    mid_in = mido.MidiFile(AI_MIDI)
    TPB_AI  = mid_in.ticks_per_beat
    print(f"输入: {AI_MIDI}")
    print(f"  TPB={TPB_AI}, len={mid_in.length:.1f}s")

    # ── 提取所有音符 ─────────────────────────────────────
    all_notes_raw = []
    for tr in mid_in.tracks:
        abs_t, open_notes = 0, {}
        for msg in tr:
            abs_t += msg.time
            if msg.type == 'note_on':
                if msg.velocity > 0:
                    open_notes[msg.note] = (abs_t, msg.velocity)
                elif msg.note in open_notes:
                    s, v = open_notes.pop(msg.note)
                    all_notes_raw.append((s, abs_t, msg.note + TRANS, v))
            elif msg.type == 'note_off' and msg.note in open_notes:
                s, v = open_notes.pop(msg.note)
                all_notes_raw.append((s, abs_t, msg.note + TRANS, v))

    all_notes_raw.sort(key=lambda x: x[0])
    print(f"  原始音符: {len(all_notes_raw)}")

    # ── 时长缩放 ────────────────────────────────────────
    AI_LAST_TICK = all_notes_raw[-1][1]
    AI_BARS  = AI_LAST_TICK / TPB_AI / 4
    STRETCH  = args.bars / AI_BARS
    SCALE    = TPB / TPB_AI * STRETCH
    print(f"  AI: {AI_BARS:.1f}小节 → 目标: {args.bars}小节 (x{STRETCH:.4f})")

    # ── 构建输出 MIDI ───────────────────────────────────
    mid_out = mido.MidiFile(type=1, ticks_per_beat=TPB)
    t0 = mido.MidiTrack([
        mido.MetaMessage('track_name', name='Tempo', time=0),
        mido.MetaMessage('set_tempo', tempo=int(60000000 / BPM), time=0),
        mido.MetaMessage('time_signature', numerator=4, denominator=4, time=0),
        mido.MetaMessage('end_of_track', time=0),
    ])
    t1 = mido.MidiTrack([
        mido.MetaMessage('track_name', name='Vocal', time=0),
        mido.Message('program_change', channel=0, program=54, time=0),
    ])
    prev_abs = 0
    for start_raw, end_raw, note, vel in all_notes_raw:
        start_out = int(start_raw * SCALE)
        end_out   = int(end_raw   * SCALE)
        delta_on  = start_out - prev_abs
        delta_off = min(end_out - start_out, TPB * 4)
        t1.append(mido.Message('note_on',  channel=0, note=note, velocity=vel, time=delta_on))
        t1.append(mido.Message('note_off', channel=0, note=note, velocity=0,  time=delta_off))
        prev_abs = end_out

    TOTAL_TICKS = args.bars * 4 * TPB
    padding = TOTAL_TICKS - prev_abs
    if padding > 0:
        t1.append(mido.Message('note_off', channel=0, note=60, velocity=0, time=padding))
    t1.append(mido.MetaMessage('end_of_track', time=0))

    mid_out.tracks.extend([t0, t1])
    os.makedirs(os.path.dirname(OUT_MIDI), exist_ok=True)
    mid_out.save(OUT_MIDI)

    # ── 验证 ────────────────────────────────────────────
    ns  = [m.note for m in t1 if m.type == 'note_on' and m.velocity > 0]
    dur = prev_abs / TPB / 4 * 60 / BPM
    last_bar = prev_abs // (TPB * 4) + 1
    print(f"\n✓ 已生成: {OUT_MIDI}")
    print(f"  TPB: {TPB_AI}→{TPB}, BPM: {BPM}, 调性: C→Eb (+{TRANS}半音)")
    print(f"  音符: {len(ns)}个, 时长: {dur:.0f}s={dur/60:.1f}min, 末音: 第{last_bar}小节")
    if ns:
        print(f"  音域: {NAMES[ns[0]%12]}{ns[0]//12-1} – {NAMES[ns[-1]%12]}{ns[-1]//12-1}")

if __name__ == '__main__':
    main()
