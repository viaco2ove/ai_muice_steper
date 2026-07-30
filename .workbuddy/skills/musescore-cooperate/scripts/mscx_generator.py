#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mscx_generator.py - MuseScore .mscx 生成器（字符串拼接法）"""
import argparse, os, sys, json, re, mido

try: sys.stdout.reconfigure(encoding='utf-8')
except: pass

TP = 480; BT = TP * 4
# chinese duration label -> ticks
DT = {'全':1920, '全分':1920, '全延':1920,
      '2分':960, '二分':960, 'half':960,
      '4分':480, '四分':480, 'quarter':480, '1拍':480,
      '8分':240, '八分':240, 'eighth':240,
      '16分':120, '十六分':120, '16th':120,
      '32分':60, '三十二分':60, '32nd':60}
DV = {'ppp':30,'pp':45,'p':60,'mp':75,'mf':85,'f':95,'ff':105,'fff':115}
PROG = {"01_吉他":"24","05_solo吉他主":"25","06_solo吉他辅1":"26","06_solo吉他辅2":"26",
        "08_节奏吉他":"24","02_主唱":"54","09_和声":"52","10_氛围垫音pad":"48",
        "11_自然白噪音":"0","12_泛音环境点缀":"48","13_轻贝斯":"33"}

def _p(ns):
    if not ns or ns in ('留白','休止','noise'): return None
    if isinstance(ns,(int,float)): return int(ns)
    m = re.match(r'([A-G])([#b]?)(\d+)', str(ns))
    if not m: return None
    s,a,o = m.group(1), m.group(2), int(m.group(3))
    v = 1 if a=='#' else (-1 if a=='b' else 0)
    return {'C':0,'D':2,'E':4,'F':5,'G':7,'A':9,'B':11}[s] + v + (o+1)*12

def _pos(ps):
    # '2.1' = beat2 sub1 (eighth units); return ticks offset within bar
    p = str(ps).replace('-', '.').split('.')
    if len(p) < 2 or not p[0].isdigit():
        return 0
    beat = int(p[0]); sub = int(p[1]) if p[1].isdigit() else 1
    return (beat - 1) * TP + (sub - 1) * 240

def df(t):  # ticks -> MuseScore durationType (English words)
    return {1920:'whole', 960:'half', 480:'quarter', 240:'eighth',
            120:'16th', 60:'32nd'}.get(t, 'quarter')

def load(name, td):
    jp = os.path.join(td, name + '.json')
    mp = os.path.join(td, name + '.mid')
    if os.path.exists(jp):
        with open(jp, encoding='utf-8') as f: d = json.load(f)
        bars = d.get('bars', [])
        if bars and isinstance(bars[0], dict) and 'beats' in bars[0]:
            n = []
            for bi, b in enumerate(bars):
                bn = b.get('bar', bi+1)
                for bt in b.get('beats', []):
                    raw_note = bt.get('actual') or bt.get('note')
                    nn = _p(raw_note)
                    if not nn: continue
                    t = (bn-1)*BT + _pos(bt.get('pos','1.1'))
                    dur = DT.get(bt.get('dur','4分'), 480)
                    n.append({'t':int(t),'n':nn,'d':dur,'name':raw_note,
                             'v':DV.get(bt.get('dynamics','mf'),85),'b':bn})
            if n: return n
        raw = d.get('notes', [])
        if raw and isinstance(raw[0], dict):
            n = []
            for r in raw:
                raw_note = r.get('actual') or r.get('note')
                nn = _p(raw_note)
                if not nn: continue
                bn = int(r.get('bar', r.get('beat_pos','1').split('.')[0]))
                t = (bn-1)*BT + _pos(r.get('beat_pos','1.1'))
                dur = DT.get(r.get('duration', r.get('dur','4分')), 480)
                n.append({'t':int(t),'n':nn,'d':dur,'name':raw_note,
                         'v':r.get('velocity', DV.get(r.get('dynamics','mf'),85)),'b':bn})
            if n: return n
    if os.path.exists(mp):
        mid = mido.MidiFile(mp); tp = mid.ticks_per_beat or TP
        n, at, op = [], 0, {}
        for g in mid.tracks[1] if len(mid.tracks) > 1 else mid.tracks[0]:
            at += g.time
            if g.type == 'note_on' and g.velocity > 0:
                op[g.note] = (at, g.velocity)
            elif (g.type == 'note_off' or (g.type == 'note_on' and g.velocity == 0)) and g.note in op:
                s, v = op.pop(g.note)
                n.append({'t':int(s),'n':g.note,'d':int(at-s),'v':v,'b':1})
        n.sort(key=lambda x: x['t']); return n
    return []

# pitch -> tpc (tonal pitch class) for treble, concert pitch
# built from note name + accidental; default C major / a minor friendly
TPC_MAP = {}
_tpc_base = {'C':14,'D':16,'E':18,'F':19,'G':21,'A':23,'B':25}
for _n,_b in _tpc_base.items():
    TPC_MAP[_n] = _b
    TPC_MAP[_n+'#'] = _b+7
    TPC_MAP[_n+'b'] = _b-7

def _tpc_for(pitch, name):
    if name:
        m = re.match(r'([A-G][#b]?)', str(name))
        if m and m.group(1) in TPC_MAP:
            return TPC_MAP[m.group(1)]
    # fall back: derive from pitch class
    pc = pitch % 12
    return {0:14,1:21,2:16,3:23,4:18,5:19,6:26,7:21,8:16,9:23,10:18,11:25}[pc]

def _duration_label(ticks):
    # split a tick count into a list of (ticks,) durations summing to it,
    # using binary (whole/half/quarter/eighth/16th) and dots not needed here
    out = []
    for unit in (1920, 960, 480, 240, 120, 60):
        while ticks >= unit:
            out.append(unit); ticks -= unit
    if ticks:  # leftover, pad to smallest
        out.append(60)
    return out or [1920]

def chord_xml(pitch, ticks, tpc, vel, lyric=''):
    parts = ['      <Chord>']
    parts.append('        <durationType>' + df(ticks) + '</durationType>')
    parts.append('        <Note>')
    parts.append('          <pitch>' + str(pitch) + '</pitch>')
    parts.append('          <tpc>' + str(tpc) + '</tpc>')
    if vel is not None:
        parts.append('          <velocity>' + format(vel/127.0, '.3f') + '</velocity>')
    parts.append('        </Note>')
    if lyric and lyric not in ('R',''):
        parts.append('        <Lyric><text>' + str(lyric) + '</text></Lyric>')
    parts.append('      </Chord>')
    return '\n'.join(parts)

def rest_xml(ticks):
    if ticks >= 1920:
        return ('        <Rest><durationType>measure</durationType>'
                '<duration>4/4</duration></Rest>')
    return '        <Rest><durationType>' + df(ticks) + '</durationType></Rest>'

def measure_xml(bar_num, bnotes, bpm, is_first):
    L = ['    <Measure>', '      <voice>']
    if is_first:
        L.append('        <TimeSig><sigN>4</sigN><sigD>4</sigD></TimeSig>')
        L.append('        <keySig><accidental>-3</accidental></keySig>')
        L.append('        <tempo><tempo>' + format(bpm/60.0, '.4f') + '</tempo></tempo>')

    if not bnotes:
        L.append('        <Rest><durationType>measure</durationType>'
                 '<duration>4/4</duration></Rest>')
    else:
        # build a timeline 0..1920, fill gaps with rests, cap each note to
        # not overflow into the next note or the bar end
        ev = sorted(bnotes, key=lambda x: x['t'] % BT)
        cursor = 0
        for i, n in enumerate(ev):
            start = n['t'] % BT
            if start > cursor:
                L.append(rest_xml(start - cursor))
            # note lasts until next event or bar end, capped by its own dur
            end = (ev[i+1]['t'] % BT) if i+1 < len(ev) else BT
            avail = end - max(start, cursor)
            dur = min(n['d'], avail) if avail > 0 else n['d']
            if dur <= 0: dur = 120
            for seg in _duration_label(dur):
                L.append(chord_xml(n['n'], seg, _tpc_for(n['n'], n.get('name')),
                                   n['v'], n.get('lyric','')))
            cursor = max(start, cursor) + dur
        if cursor < BT:
            L.append(rest_xml(BT - cursor))
    L.append('      </voice>')
    L.append('    </Measure>')
    return '\n'.join(L)

# ---- instrument definition table (modeled on 01-Guitar.mscx template) ----
# each entry: clef, instrumentId, min/max pitch, optional StringData, articulations,
# channels list of (name|None, program)
INST = {
 "01_吉他":      dict(clef="G8vb", iid="pluck.guitar.nylon-string", mn=40, mx=83,
                     strings=[40,45,50,55,59,64], frets=19),
 "08_节奏吉他":  dict(clef="G8vb", iid="pluck.guitar.nylon-string", mn=40, mx=83,
                     strings=[40,45,50,55,59,64], frets=19),
 "05_solo吉他主":dict(clef="G8vb", iid="pluck.guitar.steel-string", mn=40, mx=83,
                     strings=[40,45,50,55,59,64], frets=19),
 "06_solo吉他辅1":dict(clef="G8vb", iid="pluck.guitar.steel-string", mn=40, mx=83,
                     strings=[40,45,50,55,59,64], frets=19),
 "06_solo吉他辅2":dict(clef="G8vb", iid="pluck.guitar.steel-string", mn=40, mx=83,
                     strings=[40,45,50,55,59,64], frets=19),
 "12_泛音环境点缀":dict(clef="G8vb", iid="pluck.guitar.nylon-string", mn=40, mx=83,
                     strings=[40,45,50,55,59,64], frets=19),
 "02_主唱":      dict(clef="G", iid="voice.soprano", mn=55, mx=81),
 "09_和声":      dict(clef="G", iid="voice.alto", mn=52, mx=79),
 "10_氛围垫音pad":dict(clef="G", iid="synth.pad", mn=36, mx=96),
 "13_轻贝斯":    dict(clef="F8", iid="pluck.bass acoustic", mn=28, mx=60),
 "11_自然白噪音":dict(clef="G", iid="percussion", mn=35, mx=81),
}

ARTIC = [
 ('', 100, 100), ('staccatissimo', 100, 33), ('staccato', 100, 50),
 ('portato', 100, 67), ('tenuto', 100, 100), ('marcato', 120, 67),
 ('sforzato', 150, 100), ('sforzatoStaccato', 150, 50),
 ('marcatoStaccato', 120, 50), ('marcatoTenuto', 120, 100),
]

def part_xml(name, sid, prog):
    cfg = INST.get(name, dict(clef="G", iid="", mn=40, mx=88))
    pid = name.lower().replace(' ', '-').replace('_', '-')
    L = []
    L.append('    <Part>')
    L.append('      <Staff id="' + str(sid) + '">')
    L.append('        <StaffType group="pitched"><name>stdNormal</name></StaffType>')
    L.append('        <defaultClef>' + cfg['clef'] + '</defaultClef>')
    L.append('      </Staff>')
    L.append('      <trackName>' + name + '</trackName>')
    L.append('      <Instrument id="' + pid + '">')
    L.append('        <longName>' + name + '</longName>')
    L.append('        <shortName>' + name[:6] + '</shortName>')
    L.append('        <trackName>' + name + '</trackName>')
    L.append('        <minPitchP>' + str(cfg['mn']) + '</minPitchP>')
    L.append('        <maxPitchP>' + str(cfg['mx']) + '</maxPitchP>')
    L.append('        <minPitchA>' + str(cfg['mn']) + '</minPitchA>')
    L.append('        <maxPitchA>' + str(cfg['mx']) + '</maxPitchA>')
    if cfg.get('iid'):
        L.append('        <instrumentId>' + cfg['iid'] + '</instrumentId>')
    L.append('        <clef>' + cfg['clef'] + '</clef>')
    if cfg.get('strings'):
        sd = ['        <StringData>', '          <frets>' + str(cfg.get('frets', 19)) + '</frets>']
        for s in cfg['strings']:
            sd.append('          <string>' + str(s) + '</string>')
        sd.append('          </StringData>')
        L.extend(sd)
    for an, v, g in ARTIC:
        L.append('        <Articulation' + (' name="' + an + '"' if an else '') + '>')
        L.append('          <velocity>' + str(v) + '</velocity>')
        L.append('          <gateTime>' + str(g) + '</gateTime>')
        L.append('          </Articulation>')
    L.append('        <Channel><program value="' + str(prog) + '"/><synti>Fluid</synti></Channel>')
    L.append('        <Channel name="mute"><program value="' + str(prog) + '"/><synti>Fluid</synti></Channel>')
    L.append('        <Channel name="harmony"><program value="' + str(prog) + '"/><synti>Fluid</synti></Channel>')
    L.append('        </Instrument>')
    L.append('      </Part>')
    return '\n'.join(L)

def gen_single(name, notes, bpm):
    prog = PROG.get(name, '0')
    pid = name.lower().replace(' ','-')
    short = name[:6]
    bars = max((n['t']+n['d'] for n in notes), default=BT*52) // BT + 2
    L = []
    L.append('<?xml version="1.0" encoding="UTF-8"?>')
    L.append('<museScore version="4.00">')
    L.append('  <Score>')
    L.append('    <LayerTag id="0" tag="default"></LayerTag>')
    L.append('    <currentLayer>0</currentLayer>')
    L.append('    <Division>480</Division>')
    L.append('    <showInvisible>1</showInvisible>')
    L.append('    <showUnprintable>1</showUnprintable>')
    L.append('    <showFrames>1</showFrames>')
    L.append('    <showMargins>0</showMargins>')
    for mt in ['arranger','composer','copyright','lyricist','movementNumber',
               'movementTitle','source','translator','workNumber','workTitle']:
        val = name if mt == 'workTitle' else ''
        L.append('    <metaTag name="' + mt + '">' + val + '</metaTag>')

    L.append(part_xml(name, 1, prog))

    L.append('    <Staff id="1">')
    L.append('      <VBox>')
    L.append('        <height>10</height>')
    L.append('        <Text><style>title</style><text>' + name + '</text></Text>')
    L.append('        </VBox>')

    for m in range(1, bars+1):
        bs = (m-1) * BT
        bn = [n for n in notes if bs <= n['t'] < bs+BT]
        bn.sort(key=lambda x: x['t'])
        L.append(measure_xml(m, bn, bpm, m == 1))

    L.append('    </Staff>')
    L.append('  </Score>')
    L.append('</museScore>')
    return '\n'.join(L)

def gen_full(tracks, bpm):
    bars = max((n['t']+n['d'] for t in tracks for n in t['notes']), default=BT*52) // BT + 2
    L = []
    L.append('<?xml version="1.0" encoding="UTF-8"?>')
    L.append('<museScore version="4.00">')
    L.append('  <Score>')
    L.append('    <LayerTag id="0" tag="default"></LayerTag>')
    L.append('    <currentLayer>0</currentLayer>')
    L.append('    <Division>480</Division>')
    L.append('    <showInvisible>1</showInvisible>')
    L.append('    <showUnprintable>1</showUnprintable>')
    L.append('    <showFrames>1</showFrames>')
    L.append('    <showMargins>0</showMargins>')
    for mt in ['arranger','composer','copyright','lyricist','movementNumber',
               'movementTitle','source','translator','workNumber','workTitle']:
        val = '多轨总谱' if mt == 'workTitle' else ''
        L.append('    <metaTag name="' + mt + '">' + val + '</metaTag>')

    sid = 1
    for tr in tracks:
        L.append(part_xml(tr['name'], sid, PROG.get(tr['name'], '0')))
        sid += 1

    sid = 1
    for tr in tracks:
        notes = tr['notes']
        L.append('    <Staff id="' + str(sid) + '">')
        L.append('      <VBox>')
        L.append('        <height>10</height>')
        L.append('        <Text><style>title</style><text>' + tr['name'] + '</text></Text>')
        L.append('        </VBox>')
        for m in range(1, bars+1):
            bs = (m-1) * BT
            bn = [n for n in notes if bs <= n['t'] < bs+BT]
            bn.sort(key=lambda x: x['t'])
            L.append(measure_xml(m, bn, bpm, m == 1 and sid == 1))
        L.append('    </Staff>')
        sid += 1

    L.append('  </Score>')
    L.append('</museScore>')
    return '\n'.join(L)

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--project', required=True)
    ap.add_argument('--tracks', default='')
    ap.add_argument('-o', default='')
    ap.add_argument('--bpm', type=int, default=68)
    ap.add_argument('--full', action='store_true')
    args = ap.parse_args()

    TD = os.path.join(os.getcwd(), 'workspace', 'project', args.project, 'song_engineer', 'track')
    OUT = args.o or os.path.join(TD, 'musescore')
    os.makedirs(OUT, exist_ok=True)

    ALL = ["01_吉他","02_主唱","05_solo吉他主","06_solo吉他辅1","06_solo吉他辅2",
           "08_节奏吉他","09_和声","10_氛围垫音pad","11_自然白噪音",
           "12_泛音环境点缀","13_轻贝斯"]
    sel = [t.strip() for t in args.tracks.split(',')] if args.tracks else ALL

    data = []
    for nm in sel:
        n = load(nm, TD)
        if not n:
            print('  [skip] ' + nm)
            continue
        xml = gen_single(nm, n, args.bpm)
        out = os.path.join(OUT, nm + '.mscx')
        with open(out, 'w', encoding='utf-8') as f: f.write(xml)
        print('  [OK] ' + nm + ' (' + str(len(n)) + ' notes)')
        data.append({'name': nm, 'notes': n})

    if args.full and len(data) > 1:
        xml = gen_full(data, args.bpm)
        out = os.path.join(OUT, 'full_score.mscx')
        with open(out, 'w', encoding='utf-8') as f: f.write(xml)
        print('\n  [OK] full_score (' + str(len(data)) + ' tracks)')
    print('\noutput: ' + OUT)
