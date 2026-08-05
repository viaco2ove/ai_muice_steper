# -*- coding: utf-8 -*-
"""X Studio 歌词生成 (xstudio_lyrics 技能)
用法:
    python gen_xstudio_lyrics.py --project 走在 [--midi 02_主唱.mid] [--track 02_主唱]
    python gen_xstudio_lyrics.py --project 走在 --lyrics "门,虚,掩,..."
    python gen_xstudio_lyrics.py --project 走在 --lyrics-file lyrics.txt

X Studio 规则（与 OpenUTAU 不同）:
  - 一字对一音: 每个音符一个汉字（自动转拼音）
  - "-" = 转音/延音: 前字发音延长到当前音符（装饰音/一字多音）
  - 无 R 休止符: 音符之间留空即是休止
  - MIDI lyric 元事件: X Studio 导入时「同步导入歌词信息」→ 绝对对齐

输出 (ai-track/xstudio/):
  - {track}_xstudio_lyrics.txt   (逐音符歌词，粘贴到【编辑全部歌词】)
  - {track}_lyric.mid            (内嵌 lyric 元事件，X Studio 导入自动同步)
  - {track}_xstudio.md           (对照表: 音符#/小节.拍/音高/时值/歌词/拼音)
"""
import mido, sys, re, os, argparse
from mido.midifiles.meta import meta_charset
sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))))  # scripts→xstudio_lyrics→skills→.workbuddy→项目根
p = argparse.ArgumentParser(description="X Studio 歌词生成")
p.add_argument('--project', default='走在', help='歌曲名')
p.add_argument('--midi', default='02_主���.mid', help='MIDI 文件名（track 目录）')
p.add_argument('--track', default=None, help='轨道名（默认取 midi 文件名去扩展名）')
p.add_argument('--lyrics', help='歌词字符串: "门,虚,掩,..."（逗号分隔，无段落信息时顺序填）')
p.add_argument('--lyrics-file', help='歌词文件路径（每行一字，或 "字 拼音"）')
p.add_argument('--segments', help='段落定义 JSON: [{"name":"V1","bars":[5,12],"lyrics":[...]}]')
args = p.parse_args()

TRACK = args.track or os.path.splitext(args.midi)[0]
PROJECT = args.project
MIDI_PATH = os.path.join(ROOT, 'workspace/project', PROJECT, 'song_engineer/track', args.midi)
OUT_DIR = os.path.join(ROOT, 'workspace/project', PROJECT, 'song_engineer/ai-track/xstudio')

# ────────────────────────────────────────────────────────────
# 1. 歌词源（优先段落结构，其次平铺）
# ────────────────────────────────────────────────────────────
segments = []  # [{name, bars:[b1,b2], lyrics:[(字,拼音)]}]

if args.segments:
    import json as _json
    segs = _json.loads(args.segments)
    for s in segs:
        segments.append({'name': s['name'], 'bars': s['bars'],
                         'lyrics': [(c, '') for c in s['lyrics']]})
else:
    # 自动从 openutau_lyrics/SKILL.md 解析段落结构（按 ### 标题）
    skill_md = os.path.join(ROOT, '.workbuddy/skills/openutau_lyrics/SKILL.md')
    if args.lyrics or args.lyrics_file:
        lyrics = []
        if args.lyrics:
            for c in args.lyrics.split(','):
                c = c.strip()
                if c:
                    lyrics.append((c, ''))
        else:
            fp = args.lyrics_file if os.path.isabs(args.lyrics_file) else os.path.join(ROOT, args.lyrics_file)
            with open(fp, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    parts = line.split()
                    lyrics.append((parts[0], parts[1] if len(parts) > 1 else ''))
        # 平铺成一段（时间序）
        segments = [{'name': '全部', 'bars': [1, 999], 'lyrics': lyrics}]
    elif os.path.exists(skill_md):
        with open(skill_md, 'r', encoding='utf-8') as f:
            content = f.read()
        # 段落标题 → 小节范围
        bar_map = {
            '主歌A [Verse 1]': (5, 12), '主歌B [Verse 2]': (13, 20),
            '间奏 [Interlude]': (21, 24), '副歌 [Chorus]': (25, 32),
            '主歌A\' [Verse 3]': (33, 40), '副歌重复 [Chorus 2]': (41, 47),
            '尾奏 [Outro]': (48, 52),
        }
        sections = re.split(r'\n### ', content)
        for sec in sections:
            title = sec.split('\n')[0].strip()
            if title not in bar_map:
                continue
            rows = re.findall(r'^\| ([^|]+) \| ([^|]+) \| ([^|]+) \|', sec, re.M)
            seg_ly = []
            for r in rows:
                char, py, cv = r[0].strip(), r[1].strip(), r[2].strip()
                # 表头: "字 | 拼音 | CV音素" — 仅当 py 也是"拼音"才是表头
                if char == '字' and py == '拼音':
                    continue
                if not re.match(r'^[\u4e00-\u9fff嗯啊]$', char):
                    continue
                seg_ly.append((char, py))
            if seg_ly:
                segments.append({'name': title, 'bars': list(bar_map[title]), 'lyrics': seg_ly})
    else:
        print('[错误] 未提供歌词，且找不到 openutau_lyrics/SKILL.md', file=sys.stderr)
        sys.exit(1)

if not segments:
    print('[错误] 歌词为空', file=sys.stderr)
    sys.exit(1)

total_lyrics = sum(len(s['lyrics']) for s in segments)
print(f'歌词段落: {len(segments)} 段, �� {total_lyrics} 字')
for s in segments:
    print(f'  {s["name"]}(bar{s["bars"][0]}-{s["bars"][1]}): {len(s["lyrics"])}字')

# ────────────────────────────────────────────────────────────
# 2. 读 MIDI 音符
# ────────────────────────────────────────────────────────────
mid = mido.MidiFile(MIDI_PATH)
tp = mid.ticks_per_beat
main_track = max(range(len(mid.tracks)),
                 key=lambda i: sum(1 for m in mid.tracks[i] if m.type == 'note_on'))
at = 0
open_notes = {}
notes = []
for msg in mid.tracks[main_track]:
    at += msg.time
    if msg.type == 'note_on' and msg.velocity > 0:
        open_notes[msg.note] = (at, msg.velocity)
    elif (msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0)) and msg.note in open_notes:
        s, v = open_notes.pop(msg.note)
        notes.append({'tick': s, 'note': msg.note, 'dur': at - s, 'vel': v})
notes.sort(key=lambda x: x['tick'])
print(f'MIDI 音符: {len(notes)} 个')

def seg_notes_range(b1, b2):
    return [i for i, nn in enumerate(notes) if b1 <= nn['tick'] // (tp * 4) + 1 <= b2]

# ────────────────────────────────────────────────────────────
# 3. 填词：按段落 → 时间序 → 长音优先；未分配短音 = '-'（转音）
# ────────────────────────────────────────────────────────────
n = len(notes)
lyric_slots = [''] * n
used_idx = 0
problems = []

for seg in segments:
    b1, b2 = seg['bars']
    seg_chars = [c for c, _ in seg['lyrics']]
    idxs = seg_notes_range(b1, b2)
    if not idxs:
        problems.append(f'{seg["name"]}(bar{b1}-{b2}): 无音符，丢 {len(seg_chars)} 字')
        continue
    if len(seg_chars) > len(idxs):
        problems.append(f'{seg["name"]}(bar{b1}-{b2}): 歌词{len(seg_chars)} > 音符{len(idxs)}，截断')
        seg_chars = seg_chars[:len(idxs)]
    # 长音优先 + 时间序
    sorted_idxs = sorted(idxs, key=lambda i: (notes[i]['tick'], -notes[i]['dur']))
    top = sorted(sorted_idxs[:len(seg_chars)], key=lambda i: notes[i]['tick'])
    for k, i in enumerate(top):
        lyric_slots[i] = seg_chars[k]
    print(f'  {seg["name"]}(bar{b1}-{b2}): 音符{len(idxs)} 填{len(top)} 转音- {len(idxs)-len(top)}')

# 未分配短音 → '-'（转音延音）；若仍有歌词没填完（段落外音符），补最长音符
remaining = [i for i in range(n) if lyric_slots[i] == '']

# Intro (bar1-4) 无歌词段 = 哼唱，填 "嗯"（X Studio 不认开头转音 "-"）
hum_positions = set()  # 记录哼唱"嗯"的位置（非歌词表里的嗯）
intro_idxs = seg_notes_range(1, 4)
for i in intro_idxs:
    if lyric_slots[i] == '':
        lyric_slots[i] = '嗯'
        hum_positions.add(i)

# 剩余：'-' 转音必须紧跟前面发音（gap <= 240 ticks = 半拍），否则 '嗯' 哼唱兜底
for i in sorted(remaining):
    if lyric_slots[i] != '' or i in intro_idxs:
        continue
    gap_ok = False
    for j in range(i - 1, -1, -1):
        if lyric_slots[j] != '':
            gap_ok = notes[i]['tick'] - (notes[j]['tick'] + notes[j]['dur']) <= 240
            break
    if gap_ok:
        lyric_slots[i] = '-'
    else:
        lyric_slots[i] = '嗯'
        hum_positions.add(i)

for i in remaining:
    if lyric_slots[i] == '':
        lyric_slots[i] = '-'

r_count = sum(1 for l in lyric_slots if l == 'R')
dash_count = sum(1 for l in lyric_slots if l == '-')
hum_count = len(hum_positions)
# 歌词字 = 所有非R非-位置，减去哼唱位置（歌词表里的"嗯"也算歌词字）
word_positions = [i for i in range(n) if lyric_slots[i] not in ('R', '-') and i not in hum_positions]
word_count = len(word_positions)
print(f'\n总: {n} 音符 / {word_count} 歌词字(含歌词嗯) / {hum_count} 哼唱嗯 / {dash_count} 转音- / R: {r_count}')
print(f'歌词利用率: {word_count}/{total_lyrics} (歌词表里本身有 {sum(1 for c,_ in sum((s["lyrics"] for s in segments), []) if c == "嗯")} 个嗯)')
if problems:
    print('⚠️ 问题:')
    for pr in problems:
        print('  ', pr)

# ────────────────────────────────────────────────────────────
# 4. 输出
# ────────────────────────────────────────────────────────────
os.makedirs(OUT_DIR, exist_ok=True)
py_map = {c: py for seg in segments for c, py in seg['lyrics']}

# 4.1 X Studio 歌词 txt（逐行粘贴）
txt_path = os.path.join(OUT_DIR, f'{TRACK}_xstudio_lyrics.txt')
with open(txt_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lyric_slots))
print(f'[OK] {txt_path}')

# 4.2 内嵌 lyric 元事件的 MIDI（X Studio 导入自动同步歌词）
lyric_midi = mido.MidiFile(ticks_per_beat=mid.ticks_per_beat, charset='utf-8')
new_tracks = []
for ti, tr in enumerate(mid.tracks):
    if ti == main_track:
        nt = mido.MidiTrack()
        nt.append(mido.MetaMessage('track_name', name='Vocal', time=0))
        # 绝对时间化
        abs_t = 0
        abs_msgs = []
        for msg in tr:
            abs_t += msg.time
            abs_msgs.append((abs_t, msg))
        # 在 note_on 前插入 lyric 元事件（每个音符都要有，含转音-）
        note_idx = 0
        out = []
        prev_abs = 0
        for abs_t, msg in abs_msgs:
            if msg.type == 'note_on' and msg.velocity > 0 and note_idx < len(lyric_slots):
                lyr = lyric_slots[note_idx]
                # 所有音符都写 lyric（X Studio 导入后每个音符都有歌词槽，绝不错位）
                lm = mido.MetaMessage('lyrics', text=lyr, time=0)
                out.append((abs_t, lm))
                note_idx += 1
            out.append((abs_t, msg))
        # 写回 delta 时间
        last = 0
        for abs_t, msg in sorted(out, key=lambda x: x[0]):
            delta = abs_t - last
            last = abs_t
            nt.append(msg.copy(time=delta))
        new_tracks.append(nt)
    else:
        new_tracks.append(tr)
lyric_midi.tracks = new_tracks
midi_out = os.path.join(OUT_DIR, f'{TRACK}_lyric.mid')
lyric_midi.save(midi_out)
print(f'[OK] {midi_out}')

# 4.3 对照表 MD
md_path = os.path.join(OUT_DIR, f'{TRACK}_xstudio.md')
with open(md_path, 'w', encoding='utf-8') as f:
    f.write(f'# {TRACK} — X Studio 歌词对照表\n\n')
    f.write(f'- 音符总数: {n}\n- 歌词字数: {word_count}\n- 哼唱(嗯): {hum_count}\n- 转音符(-): {dash_count}\n- 休止符(R): {r_count}\n\n')
    f.write('| # | 小节.拍 | MIDI音 | 时值 | 歌词 | 拼音 |\n')
    f.write('|---|--------|--------|------|------|------|\n')
    for i, nn in enumerate(notes):
        bar = nn['tick'] // (tp * 4) + 1
        rem = nn['tick'] % (tp * 4)
        beat = rem // tp + 1
        sub = (rem % tp) // (tp // 4) + 1
        l = lyric_slots[i]
        py = py_map.get(l, '-') if l not in ('R', '-') else '-'
        f.write(f'| {i+1} | {bar}.{beat}.{sub} | {nn["note"]} | {nn["dur"]/tp:.2f} | {l} | {py} |\n')
print(f'[OK] {md_path}')

# 段落歌词序列验证
print('\n段落歌词序列:')
for seg in segments:
    b1, b2 = seg['bars']
    idxs = seg_notes_range(b1, b2)
    chars = ''.join(lyric_slots[i] for i in idxs if lyric_slots[i] not in ('R', '-'))
    if chars:
        print(f'  {seg["name"]}: {chars}')
