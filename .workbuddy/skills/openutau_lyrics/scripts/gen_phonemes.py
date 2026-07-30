#!/usr/bin/env python3
"""
gen_phonemes.py — 读 MIDI + 音素列表，生成 OpenUTAU 音素对照表

用法：
    # 1. 先从歌词设计文档获取音素数据（见 SKILL.md）
    # 2. 运行本脚本配对
    python gen_phonemes.py --project 走在 --midi 02_主唱.mid \\
        --phonemes "门,men,b+en 虚,xu,x+v 掩,yan,j+an ..." \\
        -o 02_主唱_phonemes.md

    # 或用 --phonemes-file 指定文件（每行: 字 拼音 音素）：
    python gen_phonemes.py --project 走在 --midi 02_主唱.mid \\
        --phonemes-file lyrics_phonemes.txt -o 02_主唱_phonemes.md

注意：音素数据（字/拼音/CV音素）需从歌词设计文档获取，
见 .workbuddy/skills/openutau_lyrics/SKILL.md 的「手工获取音素」章节。
"""
import argparse, os, sys, mido

def parse_phonemes(ph_arg: str):
    """解析 "字,拼音,音素 字,拼音,音素 ..." 格式"""
    results = []
    for part in ph_arg.strip().split():
        parts = part.split(',')
        if len(parts) == 3:
            results.append((parts[0], parts[1], parts[2]))
        else:
            print(f"[警告] 跳过无效音素段: {part}", file=sys.stderr)
    return results

def parse_phonemes_file(path: str):
    """解析音素文件（每行: 字 拼音 音素，空行/#开头的行跳过）"""
    results = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) >= 3:
                results.append((parts[0], parts[1], parts[2]))
    return results

def main():
    p = argparse.ArgumentParser(description="MIDI + 音素 → OpenUTAU 音素对照表")
    p.add_argument('--project',       required=True, help='歌曲名')
    p.add_argument('--midi',          required=True, help='MIDI 文件名（相对于 ai-track 目录）')
    p.add_argument('--phonemes',      help='音素字符串: "字,拼音,音素 ..."（空格分隔）')
    p.add_argument('--phonemes-file', help='音素文件路径（每行: 字 拼音 音素）')
    p.add_argument('-o', '--output',  help='输出 MD 文件路径（默认: ai-track/<midi>_phonemes.md）')
    p.add_argument('--tpb',          type=int, default=480, help='MIDI TPB (默认480)')
    p.add_argument('--design-bar',    type=int, default=5,   help='MIDI第1小节对应的设计文档小节 (默认5)')
    args = p.parse_args()

    # ── 解析音素 ────────────────────────────────────────
    if args.phonemes:
        PH = parse_phonemes(args.phonemes)
    elif args.phonemes_file:
        PH = parse_phonemes_file(args.phonemes_file)
    else:
        print("[错误] 必须提供 --phonemes 或 --phonemes-file", file=sys.stderr)
        sys.exit(1)

    print(f"音素数据: {len(PH)} 条")

    # ── 读取 MIDI ────────────────────────────────────────
    ROOT   = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))))
    midi_path = os.path.join(ROOT, 'workspace', 'project', args.project,
                               'song_engineer', 'ai-track', args.midi)
    if not os.path.exists(midi_path):
        print(f"[错误] 找不到 MIDI: {midi_path}", file=sys.stderr)
        sys.exit(1)

    mid  = mido.MidiFile(midi_path)
    TPB  = args.tpb
    NAMES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
    DOFF  = args.design_bar - 1  # MIDI m1 对应设计文档第几小节

    notes = []
    abs_t = 0
    for msg in mid.tracks[1] if len(mid.tracks) > 1 else mid.tracks[0]:
        abs_t += msg.time
        if msg.type == 'note_on' and msg.velocity > 0:
            beat = abs_t / TPB
            bar  = int(beat // 4) + 1
            pos  = beat % 4
            nn   = msg.note
            notes.append({
                'bar': bar, 'pos': pos,
                'note': nn,
                'name': f'{NAMES[nn%12]}{nn//12-1}',
                'midi': nn, 'vel': msg.velocity,
                'design_bar': bar + DOFF,
            })

    print(f"MIDI 音符: {len(notes)} 个")

    # ── 段落分界（可自定义） ────────────────────────────
    # 默认按设计文档估算 6 个段落
    ph_count = len(PH)
    sections = []
    if ph_count <= 40:
        sections = [(0, ph_count, '全部')]
    elif ph_count <= 80:
        half = ph_count // 2
        sections = [(0, half, '前段'), (half, ph_count, '后段')]
    elif ph_count <= 120:
        third = ph_count // 3
        sections = [(0, third, '前段'), (third, 2*third, '中段'), (2*third, ph_count, '后段')]
    else:
        sixth = ph_count // 6
        sections = [(i*sixth, (i+1)*sixth if i < 5 else ph_count,
                       f'段落{i+1}') for i in range(6)]

    # ── 生成 MD ─────────────────────────────────────────
    out_path = args.output or midi_path.replace('.mid', '_phonemes.md')
    lines = []
    lines.append(f'# {os.path.basename(midi_path).replace(".mid","")} — OpenUTAU CV Phonemes\n')
    lines.append(f'> 来源: `{os.path.basename(midi_path)}` × {len(PH)} 音素')
    lines.append(f'> 格式: 序号 | 小节.拍 | 音名 | MIDI | 力度 | 字 | 拼音 | CV音素\n')

    for si, (start, end, sec_name) in enumerate(sections):
        lines.append(f'### {sec_name} ({end-start}音素)\n')
        lines.append('| # | 设计小节 | 拍位 | 音名 | MIDI | 力度 | 字 | 拼音 | CV音素 |')
        lines.append('|:---|:--------|:-----|:-----|:-----|:----:|:--:|:----:|:-------|')
        for pi in range(start, end):
            ni = pi
            char, py, cv = PH[pi]
            if ni < len(notes):
                n   = notes[ni]
                bar_str  = f"m{n['bar']:2d}(d{n['design_bar']:2d})"
                pos_str  = f"{n['pos']:.2f}"
                note_str = n['name']
                midi_str = str(n['midi'])
                vel_str  = str(n['vel'])
            else:
                bar_str = "—"; pos_str = "—"; note_str = "—"
                midi_str = "—"; vel_str  = "—"
            lines.append(f"| {pi+1:3d} | {bar_str} | {pos_str} | {note_str} | "
                         f"{midi_str} | {vel_str} | {char} | {py} | {cv} |")
        lines.append('')

    # OpenUTAU 粘贴格式
    lines.append('## OpenUTAU 粘贴格式\n')
    lines.append('> `小节.拍  音素`，可直接粘贴到 Piano Roll 歌词栏\n')
    lines.append('```\n')
    for pi in range(min(len(notes), len(PH))):
        n  = notes[pi]
        cv = PH[pi][2]
        lines.append(f"m{n['bar']:02d}.{n['pos']:.2f}  {cv}")
    if len(notes) < len(PH):
        for pi in range(len(notes), len(PH)):
            lines.append(f"m—  {PH[pi][2]}  ← (无MIDI音符)")
    lines.append('```\n')

    lines.append('## 统计\n')
    lines.append(f'- MIDI 音符: {len(notes)} 个')
    lines.append(f'- 设计音素: {len(PH)} 条')
    lines.append(f'- 已配对: {min(len(notes), len(PH))} 个')
    if len(PH) > len(notes):
        lines.append(f'- 音符不足: {len(PH)-len(notes)} 条（尾奏等）')

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"\n✓ 已生成: {out_path}")
    print(f"  配对: {min(len(notes), len(PH))}/{len(PH)} | 缺失: {max(0, len(PH)-len(notes))}")
    print(f"\n前 10 条配对:")
    for i in range(min(10, min(len(notes), len(PH)))):
        n = notes[i]; ph = PH[i]
        print(f"  {i+1:3d}. m{n['bar']:2d}.{n['pos']:.2f} {n['name']}  {ph[0]}{ph[1]} {ph[2]}")
    if len(notes) > len(PH):
        print(f"\n  ... ({len(notes)-len(PH)} 音符无对应歌词，已留空)")

if __name__ == '__main__':
    main()