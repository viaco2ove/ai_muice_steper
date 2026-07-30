#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mscx_generator.py - MuseScore .mscx 生成器（字符串拼接法）"""
import argparse, os, sys, json, re, mido

try: sys.stdout.reconfigure(encoding='utf-8')
except: pass

TP = 480; BT = TP * 4
DT = {'16分':120,'8分':240,'4分':480,'2分':960,'全分':480,'全延':480}
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
    p = str(ps).replace('-','.').split('.')
    return 1.0 if len(p) < 2 else float(p[1])

def df(t):
    return {960:'1',480:'1/2',240:'1/4',120:'1/8',60:'1/16'}.get(t,'1/4')

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
                    nn = _p(bt.get('actual', bt.get('note')))
                    if not nn: continue
                    bp = _pos(bt.get('pos','1.1'))
                    t = int((bn-1)*BT + (bp-1)*TP)
                    n.append({'t':t,'n':nn,'d':DT.get(bt.get('dur','4分'),480),
                             'v':DV.get(bt.get('dynamics','mf'),85),'b':bn})
            if n: return n
        raw = d.get('notes', [])
        if raw and isinstance(raw[0], dict):
            n = []
            for r in raw:
                nn = _p(r.get('actual', r.get('note')))
                if not nn: continue
                bp = _pos(r.get('beat_pos','1.1'))
                bn = int(r.get('beat_pos','1').split('.')[0])
                t = int((bn-1)*BT + (bp-1)*TP)
                n.append({'t':t,'n':nn,'d':DT.get(r.get('duration','4分'),480),
                         'v':r.get('velocity',85),'b':bn})
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

def chord_xml(note):
    d = df(note['d'])
    pitch = note['n']
    vel = note['v'] / 127.0
    lyr = note.get('lyric','')
    parts = []
    parts.append('      <Chord>')
    parts.append('        <durationType>' + d + '</durationType>')
    parts.append('        <Note>')
    parts.append('          <pitch>' + str(pitch) + '</pitch>')
    parts.append('          <tpc>8</tpc>')
    parts.append('          <velocity>' + format(vel, '.3f') + '</velocity>')
    parts.append('        </Note>')
    if lyr and lyr not in ('R',''):
        parts.append('        <Lyric><text>' + lyr + '</text></Lyric>')
    parts.append('      </Chord>')
    return '\n'.join(parts)

def measure_xml(bar_num, bnotes, bpm, is_first):
    L = ['    <Measure>', '      <voice>']
    if is_first:
        L.append('        <TimeSig><sigN>4</sigN><sigD>4</sigD></TimeSig>')
        L.append('        <keySig><accidental>-1</accidental></keySig>')
        L.append('        <tempo><tempo>' + format(bpm/60.0, '.4f') + '</tempo></tempo>')
    if bnotes:
        for n in bnotes:
            L.append(chord_xml(n))
    else:
        L.append('        <Rest><durationType>measure</durationType></Rest>')
    L.append('      </voice>')
    L.append('    </Measure>')
    return '\n'.join(L)

def gen_single(name, notes, bpm):
    prog = PROG.get(name, '0')
    pid = name.lower().replace(' ','-')
    short = name[:6]
    bars = max((n['t']+n['d'] for n in notes), default=BT*52) // BT + 2

    L = []
    L.append('<?xml version="1.0" encoding="UTF-8"?>')
    L.append('<museScore version="5.00">')
    L.append('  <Score>')
    L.append('    <LayerTag id="0" tag="default"></LayerTag>')
    L.append('    <currentLayer>0</currentLayer>')
    L.append('    <Division>480</Division>')
    L.append('    <showInvisible>1</showInvisible>')
    L.append('    <showUnprintable>1</showUnprintable>')
    L.append('    <showFrames>1</showFrames>')
    L.append('    <showMargins>0</showMargins>')
    L.append('    <metaTag name="workTitle">' + name + '</metaTag>')

    L.append('    <Part>')
    L.append('      <Staff id="1">')
    L.append('        <StaffType group="itched"><name>stdNormal</name></StaffType>')
    L.append('        <defaultClef>7</defaultClef>')
    L.append('      </Staff>')
    L.append('      <trackName>' + name + '</trackName>')
    L.append('      <Instrument id="' + pid + '">')
    L.append('        <longName>' + name + '</longName>')
    L.append('        <shortName>' + short + '</shortName>')
    L.append('        <trackName>' + name + '</trackName>')
    L.append('        <Channel><program value="' + prog + '"/><synti>Fluid</synti></Channel>')
    L.append('      </Instrument>')
    L.append('    </Part>')

    L.append('    <Staff id="1">')
    L.append('      <VBox><height>10</height></VBox>')

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
    L.append('<museScore version="5.00">')
    L.append('  <Score>')
    L.append('    <LayerTag id="0" tag="default"></LayerTag>')
    L.append('    <currentLayer>0</currentLayer>')
    L.append('    <Division>480</Division>')
    L.append('    <showInvisible>1</showInvisible>')
    L.append('    <showUnprintable>1</showUnprintable>')
    L.append('    <showFrames>1</showFrames>')
    L.append('    <showMargins>0</showMargins>')
    L.append('    <metaTag name="workTitle">多轨总谱</metaTag>')

    sid = 1
    for tr in tracks:
        prog = PROG.get(tr['name'], '0')
        pid = tr['name'].lower().replace(' ','-')
        L.append('    <Part>')
        L.append('      <Staff id="' + str(sid) + '">')
        L.append('        <StaffType group="itched"><name>stdNormal</name></StaffType>')
        L.append('        <defaultClef>7</defaultClef>')
        L.append('      </Staff>')
        L.append('      <trackName>' + tr['name'] + '</trackName>')
        L.append('      <Instrument id="' + pid + '">')
        L.append('        <longName>' + tr['name'] + '</longName>')
        L.append('        <Channel><program value="' + prog + '"/><synti>Fluid</synti></Channel>')
        L.append('      </Instrument>')
        L.append('    </Part>')
        sid += 1

    sid = 1
    for tr in tracks:
        notes = tr['notes']
        L.append('    <Staff id="' + str(sid) + '">')
        L.append('      <VBox><height>10</height></VBox>')
        for m in range(1, bars+1):
            bs = (m-1) * BT
            bn = [n for n in notes if bs <= n['t'] < bs+BT]
            bn.sort(key=lambda x: x['t'])
            L.append(measure_xml(m, bn, bpm, m == 1))
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
