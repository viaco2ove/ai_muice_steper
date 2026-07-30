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
        grid = 60  # quantize to 32nd notes (ticks)
        n, at, op = [], 0, {}
        for g in mid.tracks[1] if len(mid.tracks) > 1 else mid.tracks[0]:
            at += g.time
            if g.type == 'note_on' and g.velocity > 0:
                op[g.note] = (at, g.velocity)
            elif (g.type == 'note_off' or (g.type == 'note_on' and g.velocity == 0)) and g.note in op:
                s, v = op.pop(g.note)
                qs = max(0, round(s / grid) * grid)
                qd = max(grid, round((at - s) / grid) * grid)
                n.append({'t':qs,'n':g.note,'d':qd,'v':v,'b':1})
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
    # split a tick count into standard binary durations summing to <= ticks
    # (leftover smaller than a 32nd is dropped; returns [] for ticks < 60)
    out = []
    for unit in (1920, 960, 480, 240, 120, 60):
        while ticks >= unit:
            out.append(unit); ticks -= unit
    return out

def chord_xml(notes, ticks):
    # notes: list of dicts with n,name,v,lyric at the same onset (a chord)
    parts = ['      <Chord>']
    parts.append('        <durationType>' + df(ticks) + '</durationType>')
    for n in notes:
        parts.append('        <Note>')
        parts.append('          <pitch>' + str(n['n']) + '</pitch>')
        parts.append('          <tpc>' + str(_tpc_for(n['n'], n.get('name'))) + '</tpc>')
        if n.get('v') is not None:
            parts.append('          <velocity>' + format(n['v']/127.0, '.3f') + '</velocity>')
        parts.append('        </Note>')
    # attach lyric from first note that has one
    for n in notes:
        lyr = n.get('lyric', '')
        if lyr and lyr not in ('R', ''):
            parts.append('        <Lyric><text>' + str(lyr) + '</text></Lyric>')
            break
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
        # group notes that start at the same beat into one Chord, then walk
        # the timeline filling gaps with rests and capping each chord to the
        # next onset / bar end so the measure always totals exactly 4/4
        ev = sorted(bnotes, key=lambda x: x['t'] % BT)
        groups = []
        i = 0
        while i < len(ev):
            start = ev[i]['t'] % BT
            grp = [ev[i]]; i += 1
            while i < len(ev) and (ev[i]['t'] % BT) == start:
                grp.append(ev[i]); i += 1
            groups.append((start, grp))
        cursor = 0
        for gi, (start, grp) in enumerate(groups):
            if start > cursor:
                for s in _duration_label(start - cursor):
                    L.append(rest_xml(s))
            end = groups[gi+1][0] if gi+1 < len(groups) else BT
            avail = end - max(start, cursor)
            dur = min(grp[0]['d'], avail) if avail > 0 else max(avail, 60)
            if dur <= 0: dur = 60
            segs = _duration_label(dur)
            for seg in segs:
                L.append(chord_xml(grp, seg))
            cursor = max(start, cursor) + sum(segs)
        if cursor < BT:
            for s in _duration_label(BT - cursor):
                L.append(rest_xml(s))
    L.append('      </voice>')
    L.append('    </Measure>')
    return '\n'.join(L)

# ---- instrument config loaded from musescore.conf.json ----
# structure per track: program, soundId, musesounds_library, musesounds_name,
#   midi_instrument, clef, optional strings/frets, minPitch, maxPitch
CONF = {'tracks': {}, 'default_synti': 'Fluid'}

def load_conf(td):
    global CONF
    p = os.path.join(td, 'musescore', 'musescore.conf.json')
    if os.path.exists(p):
        with open(p, encoding='utf-8') as f:
            CONF = json.load(f)
    return CONF

def track_cfg(name):
    t = CONF.get('tracks', {}).get(name)
    synti = CONF.get('default_synti', 'Fluid')
    if t:
        return {
            'clef': t.get('clef', 'G'),
            'iid': t.get('midi_instrument', t.get('soundId', '')),
            'instr_id': t.get('instrument_id', name.lower().replace(' ', '-').replace('_', '-')),
            'soundId': t.get('soundId', t.get('midi_instrument', '')),
            'mspath': t.get('musesounds_path', ''),
            'libname': t.get('museName', ''),
            'museUID': t.get('museUID', ''),
            'museName': t.get('museName', ''),
            'musePack': t.get('musePack', ''),
            'museCategory': t.get('museCategory', ''),
            'playbackSetupData': t.get('playbackSetupData', ''),
            'synti': synti,
            'prog': int(t.get('program', 0)),
            'mn': int(t.get('minPitch', 40)),
            'mx': int(t.get('maxPitch', 88)),
            'strings': t.get('strings'),
            'frets': int(t.get('frets', 19)),
        }
    # fallback defaults
    return {'clef':'G','iid':'','instr_id':'instrument','soundId':'','mspath':'',
            'libname':'','museUID':'','museName':'','musePack':'','museCategory':'',
            'playbackSetupData':'','synti':synti,'prog':0,'mn':40,'mx':88,
            'strings':None,'frets':19}

ARTIC = [
 ('', 100, 100), ('staccatissimo', 100, 33), ('staccato', 100, 50),
 ('portato', 100, 67), ('tenuto', 100, 100), ('marcato', 120, 67),
 ('sforzato', 150, 100), ('sforzatoStaccato', 150, 50),
 ('marcatoStaccato', 120, 50), ('marcatoTenuto', 120, 100),
]

def channel_xml(cfg, chan_name):
    # channel names: open (default), mute, jazz -- matches MuseScore guitar template
    # program per channel (open=main prog, mute=28, jazz=26 for guitar-ish)
    prog = cfg['prog']
    if chan_name == 'mute': prog = 28
    elif chan_name == 'jazz': prog = 26
    parts = []
    parts.append('        <Channel name="' + chan_name + '">')
    parts.append('          <program value="' + str(prog) + '"/>')
    parts.append('          <synti>' + cfg['synti'] + '</synti>')
    parts.append('          </Channel>')
    return '\n'.join(parts)

def part_xml(name, sid):
    cfg = track_cfg(name)
    instr_id = cfg['instr_id']
    L = []
    L.append('    <Part id="' + str(sid) + '">')
    L.append('      <Staff>')
    L.append('        <StaffType group="pitched"><name>stdNormal</name></StaffType>')
    L.append('        <defaultClef>' + cfg['clef'] + '</defaultClef>')
    L.append('      </Staff>')
    L.append('      <trackName>' + name + '</trackName>')
    L.append('      <Instrument id="' + instr_id + '">')
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
    L.append('        <singleNoteDynamics>0</singleNoteDynamics>')
    L.append('        <glissandoStyle>portamento</glissandoStyle>')
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
    L.append(channel_xml(cfg, 'open'))
    L.append(channel_xml(cfg, 'mute'))
    L.append(channel_xml(cfg, 'jazz'))
    L.append('        </Instrument>')
    L.append('      </Part>')
    return '\n'.join(L)

def gen_single(name, notes, bpm):
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

    L.append(part_xml(name, 1))

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
        L.append(part_xml(tr['name'], sid))
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

def audiosettings_json(track_list):
    # build audiosettings.json (MuseScore 4.7 companion file) mapping each
    # part to its MuseSounds instrument. track_list = [(name, partId), ...]
    tracks = []
    # metronome track (MuseScore always adds partId 999)
    tracks.append({
        "in": {"resourceMeta": {"attributes": {"playbackSetupData": "last.last.last",
                 "soundFontName": "MS Basic"}, "hasNativeEditorSupport": False,
                 "id": "MS Basic", "type": "fluid_soundfont", "vendor": "Fluid"},
               "unitConfiguration": {}},
        "instrumentId": "metronome",
        "out": {"balance": 0, "fxChain": {}, "volumeDb": 0},
        "partId": "999"})
    for name, pid in track_list:
        cfg = track_cfg(name)
        attrs = {}
        if cfg.get('museUID'):
            attrs = {"museCategory": cfg['museCategory'], "museName": cfg['museName'],
                     "musePack": cfg['musePack'], "museUID": cfg['museUID'],
                     "museVendorName": "Muse",
                     "playbackSetupData": cfg.get('playbackSetupData', '')}
            rmeta = {"attributes": attrs, "hasNativeEditorSupport": False,
                     "id": cfg['museUID'], "type": "muse_sampler_sound_pack",
                     "vendor": "MuseSounds"}
        else:
            rmeta = {"attributes": {"playbackSetupData": "last.last.last",
                     "soundFontName": "MS Basic"}, "hasNativeEditorSupport": False,
                     "id": "MS Basic", "type": "fluid_soundfont", "vendor": "Fluid"}
        tracks.append({
            "in": {"resourceMeta": rmeta, "unitConfiguration": {}},
            "instrumentId": cfg['instr_id'],
            "out": {"balance": 0, "fxChain": {}, "volumeDb": 0},
            "partId": str(pid),
            "soloMuteState": {"mute": False, "solo": False}})
    doc = {
        "activeSoundProfile": "",
        "aux": [
            {"out": {"balance": 0, "fxChain": {"0": {"active": True, "chainOrder": 0,
              "resourceMeta": {"attributes": {}, "hasNativeEditorSupport": True,
              "id": "Muse Reverb", "type": "muse_plugin", "vendor": "Muse"},
              "unitConfiguration": {}}}, "volumeDb": 0}},
            {"out": {"balance": 0, "fxChain": {}, "volumeDb": 0}}],
        "master": {"balance": 0, "fxChain": {}, "volumeDb": 0},
        "tracks": tracks}
    return json.dumps(doc, ensure_ascii=False, indent=4)

def container_xml(mscx_name):
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<container>\n  <rootfiles>\n'
            '    <rootfile full-path="score_style.mss"/>\n'
            '    <rootfile full-path="' + mscx_name + '"/>\n'
            '    <rootfile full-path="Thumbnails/thumbnail.png"/>\n'
            '    <rootfile full-path="automation.json"/>\n'
            '    <rootfile full-path="audiosettings.json"/>\n'
            '    <rootfile full-path="viewsettings.json"/>\n'
            '    </rootfiles>\n</container>')

def write_score_bundle(out_dir, mscx_name, mscx_xml, track_list):
    # write a single score as a MuseScore 4.7 container: mscx + companion files
    # out_dir = folder for this score; track_list = [(name, partId), ...]
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, mscx_name), 'w', encoding='utf-8') as f:
        f.write(mscx_xml)
    with open(os.path.join(out_dir, 'audiosettings.json'), 'w', encoding='utf-8') as f:
        f.write(audiosettings_json(track_list))
    with open(os.path.join(out_dir, 'automation.json'), 'w', encoding='utf-8') as f:
        f.write('[]')
    with open(os.path.join(out_dir, 'viewsettings.json'), 'w', encoding='utf-8') as f:
        f.write('{\n    "notation": {\n        "viewMode": "page"\n    }\n}')
    os.makedirs(os.path.join(out_dir, 'META-INF'), exist_ok=True)
    with open(os.path.join(out_dir, 'META-INF', 'container.xml'), 'w', encoding='utf-8') as f:
        f.write(container_xml(mscx_name))

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--project', required=True)
    ap.add_argument('--tracks', default='')
    ap.add_argument('-o', default='')
    ap.add_argument('--bpm', type=int, default=68)
    ap.add_argument('--full', action='store_true')
    ap.add_argument('--flat', action='store_true',
                    help='put all mscx in one folder (no per-score subfolders / companions)')
    args = ap.parse_args()

    TD = os.path.join(os.getcwd(), 'workspace', 'project', args.project, 'song_engineer', 'track')
    OUT = args.o or os.path.join(TD, 'musescore')
    os.makedirs(OUT, exist_ok=True)

    load_conf(TD)
    print('  loaded sound config: ' + str(len(CONF.get('tracks', {}))) + ' tracks')

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
        mscx_name = nm + '.mscx'
        if args.flat:
            with open(os.path.join(OUT, mscx_name), 'w', encoding='utf-8') as f:
                f.write(xml)
        else:
            write_score_bundle(os.path.join(OUT, nm), mscx_name, xml, [(nm, 1)])
        print('  [OK] ' + nm + ' (' + str(len(n)) + ' notes)')
        data.append({'name': nm, 'notes': n})

    if args.full and len(data) > 1:
        xml = gen_full(data, args.bpm)
        tl = [(t['name'], i+1) for i, t in enumerate(data)]
        if args.flat:
            with open(os.path.join(OUT, 'full_score.mscx'), 'w', encoding='utf-8') as f:
                f.write(xml)
        else:
            write_score_bundle(os.path.join(OUT, 'full_score'), 'full_score.mscx', xml, tl)
        print('\n  [OK] full_score (' + str(len(data)) + ' tracks)')
    print('\noutput: ' + OUT)
