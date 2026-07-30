#!/usr/bin/env python3
"""
mscx_generator.py — MuseScore 4/5 .mscx 乐谱生成器
严格参照模板: md/kb_repo/info/text_score_xml/musescore/01-Guitar.mscx
"""
import argparse, os, sys, json, re, mido
from xml.sax.saxutils import escape as x

TP = 480
PROG = {
    "01_吉他":"24","05_solo吉他主":"25","06_solo吉他辅1":"26","06_solo吉他辅2":"26",
    "08_节奏吉他":"24","02_主唱":"54","09_和声":"52","10_氛围垫音pad":"48",
    "11_自然白噪音":"0","12_泛音环境点缀":"48","13_轻贝斯":"33",
}
DT = {'16分':120,'8分':240,'4分':480,'2分':960,'全分':480,'全延':480}
DV = {'ppp':30,'pp':45,'p':60,'mp':75,'mf':85,'f':95,'ff':105,'fff':115}

def df(t):
    return {960:"1",480:"1/2",360:"3/8",320:"2/3",240:"1/4",180:"3/16",160:"1/3",120:"1/8",90:"3/32",80:"1/6",60:"1/16",30:"1/32"}.get(t,"1/4")

def _p(ns):
    if not ns or ns in ('留白','休止','noise'): return None
    if isinstance(ns,(int,float)): return int(ns)
    m=re.match(r'([A-G])([#b]?)(\d+)',str(ns))
    if not m: return None
    s,a,o=m.group(1),m.group(2),int(m.group(3))
    v=1 if a=='#' else(-1 if a=='b' else 0)
    return {'C':0,'D':2,'E':4,'F':5,'G':7,'A':9,'B':11}[s]+v+(o+1)*12

def _pos(ps):
    p=str(ps).replace('-','.').split('.')
    return 1.0 if len(p)<2 else float(p[1])

def load(name,td):
    jp=os.path.join(td,f'{name}.json');mp=os.path.join(td,f'{name}.mid')
    if os.path.exists(jp):
        with open(jp,'r',encoding='utf-8') as f: d=json.load(f)
        bars=d.get('bars',[])
        if bars and isinstance(bars[0],dict) and 'beats' in bars[0]:
            n=[]
            for bi,b in enumerate(bars):
                bn=b.get('bar',bi+1)
                for bt in b.get('beats',[]):
                    nn=_p(bt.get('actual',bt.get('note')))
                    if not nn: continue
                    bp=_pos(bt.get('pos','1.1'))
                    n.append({'t':int((bn-1)*1920+(bp-1)*TP),'n':nn,'d':DT.get(bt.get('dur','4分'),480),'v':DV.get(bt.get('dynamics','mf'),85),'b':bn})
            if n: return n
        raw=d.get('notes',[])
        if raw and isinstance(raw[0],dict):
            n=[]
            for r in raw:
                nn=_p(r.get('actual',r.get('note')))
                if not nn: continue
                bp=_pos(r.get('beat_pos','1.1'))
                bn=int(r.get('beat_pos','1').split('.')[0])
                n.append({'t':int((bn-1)*1920+(bp-1)*TP),'n':nn,'d':DT.get(r.get('duration','4分'),480),'v':r.get('velocity',85),'b':bn})
            if n: return n
    if os.path.exists(mp):
        m=mido.MidiFile(mp);tp=m.ticks_per_beat or TP
        n,a,o=[],0,{}
        for g in m.tracks[1] if len(m.tracks)>1 else m.tracks[0]:
            a+=g.time
            if g.type=='note_on' and g.velocity>0: o[g.note]=(a,g.velocity)
            elif(g.type=='note_off' or g.type=='note_on' and g.velocity==0) and g.note in o:
                s,v=o.pop(g.note); n.append({'t':int(s),'n':g.note,'d':int(a-s),'v':v,'b':1})
        n.sort(key=lambda x:x['t']); return n
    return []

def L(depth,*p): return '  '*depth+''.join(str(i) for i in p)

def gen(name,notes,bpm):
    bars=max((n['t']+n['d'] for n in notes),default=1920*52)//1920+2
    O=[]

    # Header
    O.append('<?xml version="1.0" encoding="UTF-8"?>')
    O.append('<museScore version="4.20">')
    O.append(L(1,'<Score>'))
    O.append(L(2,'<LayerTag id="0" tag="default"></LayerTag>'))
    O.append(L(2,'<currentLayer>0</currentLayer>'))
    O.append(L(2,f'<Division>{TP}</Division>'))
    O.append(L(2,'<showInvisible>1</showInvisible>'))
    O.append(L(2,'<showUnprintable>1</showUnprintable>'))
    O.append(L(2,'<showFrames>1</showFrames>'))
    O.append(L(2,'<showMargins>0</showMargins>'))
    O.append(L(2,f'<metaTag name="workTitle">{x(name)}</metaTag>'))

    # Part
    O.append(L(2,f'<Part>'))
    O.append(L(3,f'<Staff id="1">'))
    O.append(L(4,'<StaffType group="pitched"><name>stdNormal</name></StaffType>'))
    O.append(L(4,'<defaultClef>7</defaultClef>'))
    O.append(L(3,'</Staff>'))
    O.append(L(3,f'<trackName>{x(name)}</trackName>'))
    O.append(L(3,f'<Instrument id="{name.lower().replace(" ","-")}">'))
    O.append(L(4,f'<longName>{x(name)}</longName>'))
    O.append(L(4,f'<shortName>{x(name[:6])}</shortName>'))
    O.append(L(4,f'<trackName>{x(name)}</trackName>'))
    O.append(L(4,f'<Channel><program value="{PROG.get(name,"0")}"/><synti>Fluid</synti></Channel>'))
    O.append(L(3,'</Instrument>'))
    O.append(L(2,'</Part>'))

    # Staff
    O.append(L(2,f'<Staff id="1">'))
    O.append(L(3,'<VBox>'))
    O.append(L(4,'<height>10</height>'))
    O.append(L(4,f'<Text><style>title</style><text>{x(name)}</text></Text>'))
    O.append(L(3,'</VBox>'))

    for m in range(1,bars+1):
        bs=(m-1)*1920; be=bs+1920
        bn=[n for n in notes if bs<=n['t']<be]; bn.sort(key=lambda n:n['t'])
        O.append(L(3,f'<Measure>'))
        O.append(L(4,'<voice>'))
        if m==1:
            O.append(L(5,'<TimeSig><sigN>4</sigN><sigD>4</sigD></TimeSig>'))
            O.append(L(5,'<keySig><accidental>-1</accidental></keySig>'))
            O.append(L(5,f'<tempo><tempo>{bpm/60:.4f}</tempo></tempo>'))
        if bn:
            for no in bn:
                d=df(no['d'])
                O.append(L(5,'<Chord>'))
                O.append(L(6,f'<durationType>{d}</durationType>'))
                O.append(L(6,f'<duration>{no["d"]}/{TP}</duration>'))
                O.append(L(6,'<Note>'))
                O.append(L(7,f'<pitch>{no["n"]}</pitch>'))
                O.append(L(7,'<tpc>8</tpc>'))
                O.append(L(7,f'<velocity>{no["v"]/127:.3f}</velocity>'))
                O.append(L(6,'</Note>'))
                ly=no.get('lyric','')
                if ly and ly not in('R',''):
                    O.append(L(6,f'<Lyric><text>{x(ly)}</text></Lyric>'))
                O.append(L(5,'</Chord>'))
        else:
            O.append(L(5,'<Rest>'))
            O.append(L(6,'<durationType>measure</durationType>'))
            O.append(L(6,'<duration>4/4</duration>'))
            O.append(L(5,'</Rest>'))
        O.append(L(4,'</voice>'))
        O.append(L(3,'</Measure>'))

    O.append(L(2,'</Staff>'))
    O.append(L(1,'</Score>'))
    O.append('</museScore>')
    return '\n'.join(O)


def full(tracks,bpm):
    bars=max((n['t']+n['d'] for t in tracks for n in t['notes']),default=1920*52)//1920+2
    O=[]
    O.append('<?xml version="1.0" encoding="UTF-8"?>')
    O.append('<museScore version="4.20">')
    O.append(L(1,'<Score>'))
    O.append(L(2,'<LayerTag id="0" tag="default"></LayerTag>'))
    O.append(L(2,'<currentLayer>0</currentLayer>'))
    O.append(L(2,f'<Division>{TP}</Division>'))
    O.append(L(2,'<showInvisible>1</showInvisible>'))
    O.append(L(2,'<showUnprintable>1</showUnprintable>'))
    O.append(L(2,'<showFrames>1</showFrames>'))
    O.append(L(2,'<showMargins>0</showMargins>'))
    O.append(L(2,'<metaTag name="workTitle">多轨总谱</metaTag>'))

    sid=1
    for tr in tracks:
        p=PROG.get(tr['name'],'0')
        O.append(L(2,'<Part>'))
        O.append(L(3,f'<Staff id="{sid}">'))
        O.append(L(4,'<StaffType group="pitched"><name>stdNormal</name></StaffType>'))
        O.append(L(4,'<defaultClef>7</defaultClef>'))
        O.append(L(3,'</Staff>'))
        O.append(L(3,f'<trackName>{x(tr["name"])}</trackName>'))
        O.append(L(3,f'<Instrument id="{tr["name"].lower().replace(" ","-")}">'))
        O.append(L(4,f'<longName>{x(tr["name"])}</longName>'))
        O.append(L(4,f'<shortName>{x(tr["name"][:6])}</shortName>'))
        O.append(L(4,f'<Channel><program value="{p}"/><synti>Fluid</synti></Channel>'))
        O.append(L(3,'</Instrument>'))
        O.append(L(2,'</Part>'))
        sid+=1

    sid=1
    for tr in tracks:
        O.append(L(2,f'<Staff id="{sid}">'))
        for m in range(1,bars+1):
            bs=(m-1)*1920; be=bs+1920
            bn=[n for n in tr['notes'] if bs<=n['t']<be]; bn.sort(key=lambda n:n['t'])
            O.append(L(3,f'<Measure>'))
            O.append(L(4,'<voice>'))
            if m==1:
                O.append(L(5,'<TimeSig><sigN>4</sigN><sigD>4</sigD></TimeSig>'))
                O.append(L(5,'<keySig><accidental>-1</accidental></keySig>'))
                O.append(L(5,f'<tempo><tempo>{bpm/60:.4f}</tempo></tempo>'))
            if bn:
                for no in bn:
                    d=df(no['d'])
                    O.append(L(5,'<Chord>'))
                    O.append(L(6,f'<durationType>{d}</durationType>'))
                    O.append(L(6,f'<duration>{no["d"]}/{TP}</duration>'))
                    O.append(L(6,'<Note>'))
                    O.append(L(7,f'<pitch>{no["n"]}</pitch>'))
                    O.append(L(7,'<tpc>8</tpc>'))
                    O.append(L(7,f'<velocity>{no["v"]/127:.3f}</velocity>'))
                    O.append(L(6,'</Note>'))
                    ly=no.get('lyric','')
                    if ly and ly not in('R',''):
                        O.append(L(6,f'<Lyric><text>{x(ly)}</text></Lyric>'))
                    O.append(L(5,'</Chord>'))
            else:
                O.append(L(5,'<Rest>'))
                O.append(L(6,'<durationType>measure</durationType>'))
                O.append(L(6,'<duration>4/4</duration>'))
                O.append(L(5,'</Rest>'))
            O.append(L(4,'</voice>'))
            O.append(L(3,'</Measure>'))
        O.append(L(2,'</Staff>'))
        sid+=1

    O.append(L(1,'</Score>'))
    O.append('</museScore>')
    return '\n'.join(O)


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--project',required=True)
    ap.add_argument('--tracks',default='')
    ap.add_argument('-o',default='')
    ap.add_argument('--bpm',type=int,default=68)
    ap.add_argument('--full',action='store_true')
    a=ap.parse_args()

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    TD=os.path.join(ROOT,'workspace','project',a.project,'song_engineer','track')
    OUT=a.o or os.path.join(TD,'musescore')
    os.makedirs(OUT,exist_ok=True)

    ALL=["01_吉他","02_主唱","05_solo吉他主","06_solo吉他辅1","06_solo吉他辅2",
         "08_节奏吉他","09_和声","10_氛围垫音pad","11_自然白噪音",
         "12_泛音环境点缀","13_轻贝斯"]
    sel=[t.strip() for t in a.tracks.split(',')] if a.tracks else ALL

    data=[]
    for nm in sel:
        n=load(nm,TD)
        if not n: print(f"  [跳过] {nm}"); continue
        with open(os.path.join(OUT,f"{nm}.mscx"),'w',encoding='utf-8') as f:
            f.write(gen(nm,n,a.bpm))
        print(f"  [OK] {nm} ({len(n)} notes)")
        data.append({'name':nm,'notes':n})

    if a.full and len(data)>1:
        with open(os.path.join(OUT,'full_score.mscx'),'w',encoding='utf-8') as f:
            f.write(full(data,a.bpm))
        print(f"\n  [OK] 多轨总谱 ({len(data)} tracks)")
    print(f"\n输出: {OUT}")
