#!/usr/bin/env python3
"""
mscx_reader.py — 读取 .mscx 文件，提取音符/歌词/调号/BPM

用法：
    # 读取单轨
    python mscx_reader.py workspace/project/走在/song_engineer/track/musescore/02_主唱.mscx

    # 提取所有轨道并导出为 JSON
    python mscx_reader.py workspace/project/走在/song_engineer/track/musescore/full_score.mscx -o extracted.json

    # 对比两个 mscx 的差异
    python mscx_reader.py a.mscx b.mscx --diff
"""

import argparse
import os
import sys
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from typing import Optional

@dataclass
class Note:
    tick: int
    pitch: int
    duration: int      # MIDI ticks
    velocity: int
    lyric: str = ''
    bar: int = 1
    pos_in_bar: float = 0.0
    pitch_name: str = ''

@dataclass
class TrackInfo:
    name: str
    program: int
    instrument: str
    notes: list

@dataclass
class ScoreInfo:
    title: str
    composer: str
    bpm: float
    time_sig: str
    key_sig: int
    key_mode: str
    division: int
    total_bars: int
    tracks: list[TrackInfo]

# ── XML 解析 ──────────────────────────────────────────────

def parse_mscx(path: str) -> ScoreInfo:
    """解析 .mscx 文件，返回结构化数据"""
    tree = ET.parse(path)
    root = tree.getroot()

    # 找 Score 节点
    score = root.find('.//Score') or root.find('.//score') or root

    # 元数据
    meta = score.find('Meta') or score.find('meta')
    title = ''
    composer = ''
    if meta is not None:
        for tag in meta.findall('metaTag'):
            name = tag.get('name', '')
            text = ''.join(tag.itertext()).strip()
            if name == 'workTitle':
                title = text
            elif name == 'composer':
                composer = text

    # 全局属性
    division_el = score.find('Division')
    division = int(division_el.text) if division_el is not None else 480

    bpm = 120.0
    time_sig = '4/4'
    key_sig = 0
    key_mode = 'major'

    # 读取全部 Track / Voice
    tracks = []
    track_names = []

    # TrackName 元素收集
    for tn in score.findall('TrackName'):
        text = ''.join(tn.itertext()).strip()
        track_names.append(text)

    # 遍历所有 Measure 提取信息
    all_notes = []
    current_track = {'name': '', 'program': 0, 'notes': []}
    current_bpm = bpm
    track_idx = 0

    for el in score.iter():
        tag = el.tag.lower()

        if tag == 'tempo':
            tempo_el = el.find('tempo')
            if tempo_el is not None:
                try:
                    current_bpm = float(tempo_el.text) * 60
                    bpm = max(bpm, current_bpm)
                except:
                    pass

        elif tag == 'timesig':
            sn = el.find('sn')
            ss = el.find('ss')
            if sn is not None and ss is not None:
                time_sig = f"{sn.text}/{ss.text}"

        elif tag == 'keysig':
            sig_el = el.find('sig')
            accidental_el = el.find('accidental')
            keys_el = el.find('keys')
            if sig_el is not None:
                try:
                    key_sig = int(sig_el.text)
                except:
                    pass
            if keys_el is not None:
                key_text = keys_el.text or ''
                if any(k in key_text for k in ['f', 'b', 'e']) or 'flat' in key_text.lower():
                    key_mode = 'minor'

        elif tag == 'trackname':
            if current_track['name']:
                tracks.append(current_track)
                track_idx += 1
            text = ''.join(el.itertext()).strip()
            current_track = {'name': text, 'program': 0, 'notes': []}

        elif tag == 'programchange':
            pitch_el = el.find('pitch')
            prog_el  = el.find('program')
            if prog_el is not None:
                try:
                    current_track['program'] = int(prog_el.text)
                except:
                    pass

        elif tag == 'note':
            # 提取音符
            pitch_el = el.find('pitch')
            dur_el   = el.find('durationType')
            dur_d_el = el.find('Duration')
            vel_el   = el.find('velocity')
            ly_el    = el.find('Lyrics')
            dot_el   = el.find('dots')

            if pitch_el is not None:
                step_el = pitch_el.find('step')
                alt_el  = pitch_el.find('alter')
                oct_el  = pitch_el.find('octave')

                step = step_el.text if step_el is not None else 'C'
                alt  = int(alt_el.text) if alt_el is not None else 0
                octave = int(oct_el.text) if oct_el is not None else 4

                pitch = step_to_midi(step, alt, octave)
                pitch_name = f"{step}{'#' if alt > 0 else ''}{'b' if alt < 0 else ''}{octave}"

                # 时值
                duration = 480  # 默认四分
                if dur_d_el is not None:
                    d_el = dur_d_el.find('D')
                    if d_el is not None:
                        try:
                            duration = int(d_el.text)
                        except:
                            pass
                elif dur_el is not None:
                    duration = parse_duration_type(dur_el.text)

                dots = 0
                if dot_el is not None:
                    try:
                        dots = int(dot_el.text)
                    except:
                        pass

                velocity = 85
                if vel_el is not None:
                    try:
                        velocity = int(float(vel_el.text) * 127)
                    except:
                        pass

                lyric = ''
                if ly_el is not None:
                    ly_text = ly_el.find('text')
                    if ly_text is not None:
                        lyric = ''.join(ly_text.itertext()).strip()

                # 找到父级 Chord / Rest
                parent = None
                for p in el.iter():
                    if p.tag in ('Chord', 'Rest') and el in list(p):
                        parent = p
                        break

                note_obj = Note(
                    tick=0,  # 需从上下文推断
                    pitch=pitch,
                    duration=duration,
                    velocity=velocity,
                    lyric=lyric,
                    pitch_name=pitch_name,
                )
                all_notes.append(note_obj)
                current_track['notes'].append(note_obj)

    if current_track['name']:
        tracks.append(current_track)

    # 计算 tick（基于顺序累加）
    tick = 0
    bar_len = division * 4
    for n in all_notes:
        n.tick = tick
        n.bar = tick // bar_len + 1
        n.pos_in_bar = (tick % bar_len) / division
        tick += n.duration

    total_bars = max((n.bar for n in all_notes), default=1)

    return ScoreInfo(
        title=title,
        composer=composer,
        bpm=bpm,
        time_sig=time_sig,
        key_sig=key_sig,
        key_mode=key_mode,
        division=division,
        total_bars=total_bars,
        tracks=tracks,
    )


def step_to_midi(step: str, alter: int, octave: int) -> int:
    """音名+升降号+八度 -> MIDI 编号"""
    step_map = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
    if step in step_map:
        return step_map[step] + alter + (octave + 1) * 12
    return 60


def parse_duration_type(dur_str: str) -> int:
    """durationType 字符串 -> ticks"""
    dur_map = {
        'whole': 3840, '1': 3840,
        'half': 1920, '1/2': 1920,
        'quarter': 960, '1/4': 960,
        'eighth': 480, '1/8': 480,
        '16th': 240, '1/16': 240,
        '32nd': 120, '1/32': 120,
        'measure': 1920,
    }
    return dur_map.get(dur_str.strip(), 480)


# ── 输出格式化 ───────────────────────────────────────────

def format_score_info(score: ScoreInfo) -> str:
    """格式化输出乐谱信息"""
    lines = []
    lines.append(f"标题: {score.title or '(无标题)'}")
    lines.append(f"速度: {score.bpm:.0f} BPM")
    lines.append(f"拍号: {score.time_sig}")
    lines.append(f"调号: {score.key_sig} ({score.key_mode})")
    lines.append(f"分轨: {len(score.tracks)} 条")
    lines.append(f"总小节: {score.total_bars}")
    lines.append('')
    for i, tr in enumerate(score.tracks):
        tr_name = tr.get('name', f'轨道{i+1}') if isinstance(tr, dict) else (tr.name or f'轨道{i+1}')
        tr_prog = tr.get('program', 0) if isinstance(tr, dict) else tr.program
        tr_notes = tr.get('notes', []) if isinstance(tr, dict) else tr.notes
        lines.append(f"  [{i+1}] {tr_name}")
        lines.append(f"       音色: program={tr_prog}, 音符数={len(tr_notes)}")
        if tr_notes:
            first = tr_notes[0]
            last  = tr_notes[-1]
            pfirst = first.pitch_name if hasattr(first, 'pitch_name') else str(first.get('pitch_name', ''))
            plast  = last.pitch_name  if hasattr(last,  'pitch_name') else str(last.get('pitch_name', ''))
            lines.append(f"       音域: {pfirst} ~ {plast}")
            flyric = first.lyric if hasattr(first, 'lyric') else str(first.get('lyric', ''))
            if flyric:
                lines.append(f"       首音歌词: {flyric}")
    return '\n'.join(lines)


def export_to_json(score: ScoreInfo, out_path: str):
    """导出为 JSON（dataclass -> dict）"""
    def notes_to_dict(notes):
        return [asdict(n) for n in notes]
    data = {
        'title': score.title,
        'bpm': score.bpm,
        'time_sig': score.time_sig,
        'key_sig': score.key_sig,
        'division': score.division,
        'total_bars': score.total_bars,
        'tracks': [
            {
                'name': tr.name,
                'program': tr.program,
                'note_count': len(tr.notes),
                'notes': notes_to_dict(tr.notes),
            }
            for tr in score.tracks
        ]
    }
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"已导出 JSON: {out_path}")


def diff_scores(a: ScoreInfo, b: ScoreInfo):
    """对比两个乐谱的差异"""
    print("=== 对比差异 ===")
    print(f"  标题: {a.title} vs {b.title}")
    print(f"  BPM: {a.bpm:.0f} vs {b.bpm:.0f}")
    print(f"  轨数: {len(a.tracks)} vs {len(b.tracks)}")
    print(f"  总小节: {a.total_bars} vs {b.total_bars}")
    print()
    for i, (ta, tb) in enumerate(zip(a.tracks, b.tracks)):
        da = len(ta.notes)
        db = len(tb.notes)
        if da != db:
            print(f"  轨道 {i+1} '{ta.name}': {da} notes vs {db} notes  ***")
        else:
            print(f"  轨道 {i+1} '{ta.name}': {da} notes (相同)")


# ── 主程序 ───────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="读取 .mscx 乐谱文件")
    p.add_argument('mscx', nargs='+', help='.mscx 文件路径')
    p.add_argument('-o', '--output', help='导出为 JSON 文件')
    p.add_argument('--diff', action='store_true', help='对比两个 mscx')
    p.add_argument('--summary', action='store_true', help='仅显示概要')
    args = p.parse_args()

    if len(args.mscx) == 0:
        print("[错误] 请提供 .mscx 文件路径")
        sys.exit(1)

    if args.diff and len(args.mscx) == 2:
        s1 = parse_mscx(args.mscx[0])
        s2 = parse_mscx(args.mscx[1])
        diff_scores(s1, s2)
        return

    # 逐文件解析
    for path in args.mscx:
        if not os.path.exists(path):
            print(f"[错误] 文件不存在: {path}")
            continue

        print(f"\n{'='*50}")
        print(f"文件: {path}")

        try:
            score = parse_mscx(path)
        except Exception as e:
            print(f"[解析错误] {e}")
            import traceback; traceback.print_exc()
            continue

        print(format_score_info(score))

        if args.output and len(args.mscx) == 1:
            export_to_json(score, args.output)

        if args.summary:
            continue

        # 详细音符列表（前20条 + 后10条）
        for ti, tr in enumerate(score.tracks):
            if not tr.notes:
                continue
            print(f"\n  轨道 {ti+1} '{tr.name}' 音符列表:")
            for n in tr.notes[:20]:
                print(f"    m{n.bar:2d}.{n.pos_in_bar:.2f}  "
                      f"{n.pitch_name:5s} vel={n.velocity:3d}  "
                      f"{n.duration:4d}t  "
                      f"{'lyric='+n.lyric if n.lyric else ''}")
            if len(tr.notes) > 30:
                print(f"    ... ({len(tr.notes)-30} 条省略)")
                for n in tr.notes[-10:]:
                    print(f"    m{n.bar:2d}.{n.pos_in_bar:.2f}  "
                          f"{n.pitch_name:5s} vel={n.velocity:3d}  "
                          f"{n.duration:4d}t  "
                          f"{'lyric='+n.lyric if n.lyric else ''}")

if __name__ == '__main__':
    main()