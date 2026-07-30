#!/usr/bin/env python3
"""
mscx_generator.py — MuseScore .mscx 乐谱生成器（MuseScore 4 兼容格式）

参考: My_First_Score.mscx (官方模板) + Dawn.mscx
规范: https://github.com/musescore/MuseScore
"""

import argparse, os, sys, json, re, mido
from xml.sax.saxutils import escape as xml_escape

# ── 工具函数 ───────────────────────────────────────────────
NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
DUR_TICKS  = {'16分': 120, '8分': 240, '4分': 480, '2分': 960, '全分': 480, '全延': 480}
DYN_VEL    = {'ppp': 30, 'pp': 45, 'p': 60, 'mp': 75, 'mf': 85, 'f': 95, 'ff': 105, 'fff': 115}

def midi_to_name(n: int) -> str:
    return f"{NOTE_NAMES[n%12]}{n//12-1}"

def midi_to_ms_pitch(n: int) -> tuple:
    """MIDI编号 -> (step, alter, octave)"""
    step  = NOTE_NAMES[n % 12].replace('#', '')
    alter = 1 if '#' in NOTE_NAMES[n % 12] else 0
    oct_  = n // 12 - 1
    return step, alter, oct_

def dur_to_fraction(ticks: int) -> str:
    """480 ticks = quarter = 1/4"""
    map_ = {960: "1", 480: "1/4", 240: "1/8", 120: "1/16", 60: "1/32"}
    return map_.get(ticks, f"1/{480//max(1,ticks//240)}")

def _pitch(note_str) -> int | None:
    if not note_str or note_str in ('留白', '休止', 'noise'):
        return None
    if isinstance(note_str, (int, float)):
        return int(note_str)
    m = re.match(r"([A-G])([#b]?)(\d+)", str(note_str))
    if not m:
        return None
    step = m.group(1)
    alt  = 1 if m.group(2) == '#' else (-1 if m.group(2) == 'b' else 0)
    return {'C':0,'D':2,'E':4,'F':5,'G':7,'A':9,'B':11}[step] + alt + (int(m.group(3))+1)*12

def _pos(pos_str: str, default_bar=1, default_beat=1.0):
    """解析位置 "1.1" / "1.2" / "1.2.1" -> (bar, beat_float)"""
    pos_str = str(pos_str).replace('-', '.').strip()
    parts = pos_str.split('.')
    # 取前两段作为 bar 和 beat
    bar = int(parts[0]) if parts and parts[0].isdigit() else default_bar
    beat = float(parts[1]) if len(parts) > 1 and parts[1].isdigit() else default_beat
    return bar, beat

# ── 读取音符数据 ─────────────────────────────────────────
def load_notes(name: str, track_dir: str) -> list[dict]:
    """从 JSON 或 MID 读取音符列表"""
    json_path = os.path.join(track_dir, f"{name}.json")
    mid_path  = os.path.join(track_dir, f"{name}.mid")
    tp, bar_ticks = 480, 480 * 4

    # 格式1: {bars: [{beats: [...]}]}
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            d = json.load(f)
        bars = d.get('bars', [])
        if bars and isinstance(bars[0], dict) and 'beats' in bars[0]:
            notes = []
            for bar_idx, bar in enumerate(bars):
                # 用 JSON bar 字段作为小节号（不是 pos 字符串的循环值）
                bar_num = bar.get('bar', bar_idx + 1)
                for beat in bar.get('beats', []):
                    # pos 是拍位字符串（如 '1.1'/'3-4'），解析为 (beat_in_bar, pos_in_beat)
                    beat_bar, beat_pos = _pos(beat.get('pos', '1.1'))
                    nn = _pitch(beat.get('actual', beat.get('note')))
                    if nn is None:
                        continue
                    vel = DYN_VEL.get(beat.get('dynamics', 'mf'), 85)
                    lyric = beat.get('lyric', bar.get('lyric', ''))
                    tick = int((bar_num-1)*bar_ticks + (beat_pos-1)*tp)
                    notes.append({'tick': tick, 'note': nn, 'dur': DUR_TICKS.get(beat.get('dur','4分'), 480),
                                  'vel': vel, 'lyric': lyric, 'bar': bar_num})
            return notes

        # 格式2: {notes: [{beat_pos, actual, duration}]}
        raw = d.get('notes', [])
        if raw and isinstance(raw[0], dict):
            notes = []
            for n in raw:
                bar_num, beat_pos = _pos(n.get('beat_pos', '1.1'))
                nn = _pitch(n.get('actual', n.get('note')))
                if nn is None:
                    continue
                vel = n.get('velocity', 85)
                lyric = n.get('lyric', '')
                tick = int((bar_num-1)*bar_ticks + (beat_pos-1)*tp)
                notes.append({'tick': tick, 'note': nn, 'dur': DUR_TICKS.get(n.get('duration', '4分'), 480),
                              'vel': vel, 'lyric': lyric, 'bar': bar_num})
            if notes:
                return notes

    # 格式3: MIDI fallback
    if os.path.exists(mid_path):
        mid = mido.MidiFile(mid_path)
        tp_ = mid.ticks_per_beat or 480
        notes = []; abs_t = 0; open_n = {}
        for msg in mid.tracks[1] if len(mid.tracks) > 1 else mid.tracks[0]:
            abs_t += msg.time
            if msg.type == 'note_on' and msg.velocity > 0:
                open_n[msg.note] = (abs_t, msg.velocity)
            elif (msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0)) and msg.note in open_n:
                s, v = open_n.pop(msg.note)
                notes.append({'tick': int(s), 'note': msg.note, 'dur': int(abs_t-s), 'vel': v, 'lyric': '', 'bar': 1})
        notes.sort(key=lambda x: x['tick'])
        return notes

    return []

# ── 音色映射 ─────────────────────────────────────────────
PROGRAM_MAP = {
    "01_吉他": 24, "05_solo吉他主": 25, "06_solo吉他辅1": 26,
    "06_solo吉他辅2": 26, "08_节奏吉他": 24,
    "02_主唱": 54, "09_和声": 52, "10_氛围垫音pad": 48,
    "11_自然白噪音": 0, "12_泛音环境点缀": 48, "13_轻贝斯": 33,
}
INST_MAP = {
    24: ("Nylon Guitar", "Nyl.Gtr"),  25: ("Steel Guitar", "Stl.Gtr"),
    26: ("Electric Guitar", "E.Gtr"),   33: ("Electric Bass", "E.Bass"),
    48: ("Strings", "Str."),           52: ("Choir", "Choir"),
    54: ("Voice", "Voice"),
}

def inst_name(prog: int) -> tuple:
    return INST_MAP.get(prog, ("Piano", "Pno."))

# ── XML 生成 ─────────────────────────────────────────────
def xml(text: str) -> str:
    return xml_escape(str(text))

def gen_single_mscx(name: str, notes: list, program: int, bpm: int) -> str:
    """生成单轨 MuseScore 4 .mscx"""
    tp, bar_ticks = 480, 480 * 4
    total_bars = max((n['tick']+n['dur'] for n in notes), default=bar_ticks*52) // bar_ticks + 2
    instr_long, instr_short = inst_name(program)

    L = []  # lines collector

    def w(tag, content='', indent=0, attrs=''):
        attrs = (' '+attrs) if attrs else ''
        if content:
            L.append(f"{'  '*indent}<{tag}{attrs}>{content}</{tag}>")
        else:
            L.append(f"{'  '*indent}<{tag}{attrs}/>")

    def wi(indent, *parts):
        L.append(f"{'  '*indent}{'  '.join(str(p) for p in parts)}")

    # ── Header ──────────────────────────────────────────
    wi(0, '<?xml version="1.0" encoding="UTF-8"?>')
    wi(0, f'<museScore version="4.20" minorVersion="20">')
    wi(0, '<Score>')
    wi(1, '<LayerTag id="0" tag="default"/>')
    wi(1, '<currentLayer>0</currentLayer>')
    wi(1, f'<Division>{tp}</Division>')
    wi(1, '<Style>')
    wi(2, '<spatium>1.6</spatium>')
    wi(1, '</Style>')
    wi(1, '<showInvisible>1</showInvisible>')
    wi(1, '<showUnprintable>1</showUnprintable>')
    wi(1, '<showFrames>1</showFrames>')
    wi(1, '<showMargins>0</showMargins>')
    wi(1, f'<metaTag name="workTitle">{xml(name)}</metaTag>')
    wi(1, f'<metaTag name="title">{xml(name)}</metaTag>')

    # ── Part ────────────────────────────────────────────
    wi(1, '<Part>')
    wi(2, '<Staff id="1">')
    wi(3, '<StaffType group="pitched"><name>stdNormal</name></StaffType>')
    wi(3, '<defaultClef>7</defaultClef>')   # G clef
    wi(2, '</Staff>')
    wi(2, f'<trackName>{xml(name)}</trackName>')
    wi(2, '<Instrument>')
    wi(3, f'<longName>{xml(instr_long)}</longName>')
    wi(3, f'<shortName>{xml(instr_short)}</shortName>')
    wi(3, f'<trackName>{xml(name)}</trackName>')
    wi(3, '<Channel>')
    wi(4, f'<program value="{program}"/>')
    wi(4, '<synti>Fluid</synti>')
    wi(3, '</Channel>')
    wi(2, '</Instrument>')
    wi(1, '</Part>')

    # ── Staff ───────────────────────────────────────────
    wi(1, '<Staff id="1">')

    # 逐小节
    for bar_num in range(1, total_bars + 1):
        bar_start = (bar_num - 1) * bar_ticks
        bar_end   = bar_start + bar_ticks
        bar_notes = [n for n in notes if bar_start <= n['tick'] < bar_end]
        bar_notes.sort(key=lambda x: x['tick'])

        wi(2, '<Measure>')
        wi(3, '<voice>')

        # 小节头（前4小节加调号/拍号/速度）
        if bar_num <= 4:
            if bar_num == 1:
                wi(4, '<keySig><accidental>-1</accidental></keySig>')
                wi(4, '<timeSig><sigN>4</sigN><sigD>4</sigD></timeSig>')
                wi(4, f'<tempo><tempo>{bpm/60:.4f}</tempo></tempo>')

        # 音符
        if bar_notes:
            for n in bar_notes:
                step, alter, oct_ = midi_to_ms_pitch(n['note'])
                dur_frac = dur_to_fraction(n['dur'])
                vel = n['vel']
                wi(4, '<Chord>')
                wi(5, f'<durationType>{dur_frac}</durationType>')
                wi(5, f'<Note>')
                wi(6, f'<pitch>{n["note"]}</pitch>')
                wi(6, f'<tpc>{7 if step=="C" else 8}</tpc>')
                wi(6, f'<velocity>{vel/127:.3f}</velocity>')
                wi(5, '</Note>')
                lyric = n.get('lyric', '')
                if lyric and lyric not in ('R', ''):
                    wi(5, f'<Lyric><text>{xml(lyric)}</text></Lyric>')
                wi(4, '</Chord>')
        else:
            wi(4, '<Rest>')
            wi(5, '<durationType>measure</durationType>')
            wi(5, '<duration>4/4</duration>')
            wi(4, '</Rest>')

        wi(3, '</voice>')
        wi(2, '</Measure>')

    wi(1, '</Staff>')
    wi(0, '</Score>')
    wi(0, '</museScore>')

    return '\n'.join(L)


def gen_full_score_mscx(tracks: list[dict], bpm: int) -> str:
    """生成多轨总谱"""
    tp, bar_ticks = 480, 480 * 4

    L = []
    def wi(indent, *parts): L.append(f"{'  '*indent}{'  '.join(str(p) for p in parts)}")

    wi(0, '<?xml version="1.0" encoding="UTF-8"?>')
    wi(0, '<museScore version="4.20" minorVersion="20">')
    wi(0, '<Score>')
    wi(1, '<LayerTag id="0" tag="default"/>')
    wi(1, '<currentLayer>0</currentLayer>')
    wi(1, f'<Division>{tp}</Division>')
    wi(1, '<Style><spatium>1.6</spatium></Style>')
    wi(1, '<showInvisible>1</showInvisible>')
    wi(1, '<showUnprintable>1</showUnprintable>')
    wi(1, '<showFrames>1</showFrames>')
    wi(1, '<showMargins>0</showMargins>')
    wi(1, '<metaTag name="workTitle">走在 - 多轨总谱</metaTag>')

    total_bars = 0
    for tr in tracks:
        tb = max((n['tick']+n['dur'] for n in tr['notes']), default=0) // bar_ticks + 2
        total_bars = max(total_bars, tb)

    # Parts
    staff_id = 1
    for tr in tracks:
        program = tr['program']
        instr_long, instr_short = inst_name(program)
        wi(1, '<Part>')
        wi(2, f'<Staff id="{staff_id}">')
        wi(3, '<StaffType group="pitched"><name>stdNormal</name></StaffType>')
        wi(3, '<defaultClef>7</defaultClef>')
        wi(2, '</Staff>')
        wi(2, f'<trackName>{xml(tr["name"])}</trackName>')
        wi(2, '<Instrument>')
        wi(3, f'<longName>{xml(instr_long)}</longName>')
        wi(3, f'<shortName>{xml(instr_short)}</shortName>')
        wi(3, '<Channel>')
        wi(4, f'<program value="{program}"/>')
        wi(4, '<synti>Fluid</synti>')
        wi(3, '</Channel>')
        wi(2, '</Instrument>')
        wi(1, '</Part>')
        staff_id += 1

    # Staffs
    staff_id = 1
    for tr in tracks:
        notes = tr['notes']
        wi(1, f'<Staff id="{staff_id}">')
        for bar_num in range(1, total_bars + 1):
            bar_start = (bar_num - 1) * bar_ticks
            bar_end   = bar_start + bar_ticks
            bar_notes = [n for n in notes if bar_start <= n['tick'] < bar_end]
            bar_notes.sort(key=lambda x: x['tick'])

            wi(2, '<Measure>')
            wi(3, '<voice>')
            if bar_num <= 4:
                if bar_num == 1:
                    wi(4, '<keySig><accidental>-1</accidental></keySig>')
                    wi(4, '<timeSig><sigN>4</sigN><sigD>4</sigD></timeSig>')
                    wi(4, f'<tempo><tempo>{bpm/60:.4f}</tempo></tempo>')

            if bar_notes:
                for n in bar_notes:
                    dur_frac = dur_to_fraction(n['dur'])
                    vel = n['vel']
                    wi(4, '<Chord>')
                    wi(5, f'<durationType>{dur_frac}</durationType>')
                    wi(5, '<Note>')
                    wi(6, f'<pitch>{n["note"]}</pitch>')
                    wi(5, '</Note>')
                    lyric = n.get('lyric', '')
                    if lyric and lyric not in ('R', ''):
                        wi(5, f'<Lyric><text>{xml(lyric)}</text></Lyric>')
                    wi(4, '</Chord>')
            else:
                wi(4, '<Rest>')
                wi(5, '<durationType>measure</durationType>')
                wi(5, '<duration>4/4</duration>')
                wi(4, '</Rest>')

            wi(3, '</voice>')
            wi(2, '</Measure>')
        wi(1, '</Staff>')
        staff_id += 1

    wi(0, '</Score>')
    wi(0, '</museScore>')
    return '\n'.join(L)


# ── 主程序 ───────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(description="生成 MuseScore .mscx 乐谱")
    p.add_argument('--project',  required=True)
    p.add_argument('--tracks',   help='逗号分隔轨名（默认全部）')
    p.add_argument('-o', '--output', default='')
    p.add_argument('--bpm', type=int, default=68)
    p.add_argument('--full', action='store_true')
    args = p.parse_args()

    ROOT     = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    TRACK_DIR = os.path.join(ROOT, 'workspace', 'project', args.project, 'song_engineer', 'track')
    OUT_DIR  = args.output or os.path.join(TRACK_DIR, 'musescore')
    os.makedirs(OUT_DIR, exist_ok=True)

    ALL = ["01_吉他","02_主唱","05_solo吉他主","06_solo吉他辅1","06_solo吉他辅2",
           "08_节奏吉他","09_和声","10_氛围垫音pad","11_自然白噪音",
           "12_泛音环境点缀","13_轻贝斯"]
    selected = [t.strip() for t in args.tracks.split(',')] if args.tracks else ALL

    all_data = []
    for name in selected:
        notes = load_notes(name, TRACK_DIR)
        if not notes:
            print(f"  [跳过] {name} (无可用音符)")
            continue
        program = PROGRAM_MAP.get(name, 0)
        out = os.path.join(OUT_DIR, f"{name}.mscx")
        with open(out, 'w', encoding='utf-8') as f:
            f.write(gen_single_mscx(name, notes, program, args.bpm))
        print(f"  [OK] {name} -> {name}.mscx ({len(notes)} notes)")
        all_data.append({'name': name, 'notes': notes, 'program': program})

    if args.full and len(all_data) > 1:
        out = os.path.join(OUT_DIR, 'full_score.mscx')
        with open(out, 'w', encoding='utf-8') as f:
            f.write(gen_full_score_mscx(all_data, args.bpm))
        print(f"\n  [OK] 多轨总谱 -> full_score.mscx ({len(all_data)} tracks)")

    print(f"\n输出: {OUT_DIR}")
    print("用 MuseScore Studio 打开 .mscx 即可查看/编辑")

if __name__ == '__main__':
    main()