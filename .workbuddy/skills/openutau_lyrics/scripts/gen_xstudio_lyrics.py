# -*- coding: utf-8 -*-
"""02_主唱 MIDI → X Studio 歌词对齐生成 (openutau_lyrics 技能)
用法:
    python gen_xstudio_lyrics.py --project 走在 [--midi 02_主唱.mid]
输入: workspace/project/{歌名}/song_engineer/track/02_主唱.mid
歌词: 从本技能 SKILL.md 歌词表解析（按段落匹配小节范围）
输出: 
  - ai-track/xstudio/02_主唱_xstudio_lyrics.txt   (逐音符歌词, R=休止, X Studio 直接导入)
  - ai-track/xstudio/02_主唱_xstudio_lyrics_pinyin.txt (歌词+拼音+音素)
  - ai-track/xstudio/02_主唱_xstudio.md          (完整对照表)
"""
import mido, sys, re, os, argparse
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))))  # scripts→openutau_lyrics→skills→.workbuddy→项目根
p = argparse.ArgumentParser(description="MIDI → X Studio 歌词对齐")
p.add_argument('--project', default='走在', help='歌曲名')
p.add_argument('--midi', default='02_主唱.mid', help='MIDI 文件名（track 目录）')
p.add_argument('--track', default='02_主唱', help='轨道名')
args = p.parse_args()

PROJECT = args.project
MIDI = os.path.join(ROOT, 'workspace/project', PROJECT, 'song_engineer/track', args.midi)
SKILL = os.path.join(ROOT, '.workbuddy/skills/openutau_lyrics/SKILL.md')
OUT_DIR = os.path.join(ROOT, 'workspace/project', PROJECT, 'song_engineer/ai-track/xstudio')

# ---- 1. 解析 SKILL.md 歌词表 ----
with open(SKILL, 'r', encoding='utf-8') as f:
    content = f.read()

# 提取各段表格（按标题切分）
sections = re.split(r'\n### ', content)
lyric_segments = []  # (段名, [(字,拼音,音素)])
for sec in sections:
    title = sec.split('\n')[0].strip()
    rows = re.findall(r'^\| ([^|]+) \| ([^|]+) \| ([^|]+) \|', sec, re.M)
    seg = []
    for r in rows:
        char, pinyin, cv = r[0].strip(), r[1].strip(), r[2].strip()
        # 只过滤表头行
        if char == '字' and pinyin == '拼音':
            continue
        if cv and re.match(r'^[a-zA-Z]+(\+[a-zA-Z]+)?$', cv) and re.match(r'^[\u4e00-\u9fff嗯啊]$', char):
            seg.append((char, pinyin, cv))
    if seg and ('主歌A' in title or '主歌B' in title or '间奏' in title or '副歌' in title or '尾奏' in title):
        lyric_segments.append((title, seg))

all_lyrics = []
for name, seg in lyric_segments:
    all_lyrics.extend(seg)
print(f'歌词段数: {len(lyric_segments)}, 总歌词数: {len(all_lyrics)}')
for name, seg in lyric_segments:
    print(f'  {name}: {len(seg)}字  {"".join(c for c,_,_ in seg)[:15]}...')

# ---- 2. 读 MIDI 音符 ----
mid = mido.MidiFile(MIDI)
tp = mid.ticks_per_beat
at = 0
open_notes = {}
notes = []
for msg in mid.tracks[1]:
    at += msg.time
    if msg.type == 'note_on' and msg.velocity > 0:
        open_notes[msg.note] = (at, msg.velocity)
    elif (msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0)) and msg.note in open_notes:
        s, v = open_notes.pop(msg.note)
        notes.append({'tick': s, 'note': msg.note, 'dur': at - s, 'vel': v})
notes.sort(key=lambda x: x['tick'])
print(f'MIDI 音符数: {len(notes)}')

# ---- 3. 段落→小节映射 ----
# 段落名匹配歌词段
seg_order = ['主歌A', '主歌B', '间奏', '副歌', '主歌A', '副歌重复', '尾奏']
bar_segments = [  # (小节起, 小节止, 歌词段索引)
    (5, 12, 0),   # V1 主歌A
    (13, 20, 1),  # V2 主歌B
    (21, 24, 2),  # 间奏
    (25, 32, 3),  # 副歌1
    (33, 40, 4),  # 主歌A'
    (41, 47, 5),  # 副歌2
    (48, 52, 6),  # 尾奏
]

# ---- 4. 逐段填词 ----
# 先构建 304 长度的歌词列表，默认 R
n = len(notes)
lyrics = ['R'] * n
used_lyric_idx = 0

def seg_notes_range(b1, b2):
    """返回该小节范围内的音符索引列表"""
    idxs = []
    for i, nn in enumerate(notes):
        bar = nn['tick'] // (tp * 4) + 1
        if b1 <= bar <= b2:
            idxs.append(i)
    return idxs

problems = []
for b1, b2, seg_idx in bar_segments:
    seg_name, seg = lyric_segments[seg_idx]
    seg_chars = [c for c, _, _ in seg]
    idxs = seg_notes_range(b1, b2)
    if not idxs:
        problems.append(f'{seg_name}(bar{b1}-{b2}): 无音符!')
        continue
    if len(seg_chars) > len(idxs):
        problems.append(f'{seg_name}(bar{b1}-{b2}): 歌词{len(seg_chars)} > 音符{len(idxs)}, 差{len(seg_chars)-len(idxs)}')
        # 截断放不下，多出的歌词标记
        seg_chars = seg_chars[:len(idxs)]
    # 按时间顺序排序
    sorted_idxs = sorted(idxs, key=lambda i: notes[i]['tick'])
    # 填词策略：保持时间顺序，装饰音(短音)优先留 R
    # 步骤1: 找候选 = 时长>=阈值的音符（按时间序），阈值从高到低降，直到候选>=歌词数
    threshold = 360  # 从 3拍 开始
    while threshold >= 60:
        cands = [i for i in sorted_idxs if notes[i]['dur'] >= threshold]
        if len(cands) >= len(seg_chars):
            break
        threshold -= 30
    # 兜底：候选不够就全部音符都算候选（保证歌词全部填上）
    if len(cands) < len(seg_chars):
        cands = sorted_idxs[:]
    # 取前 N 个（时间有序），填词
    fill = cands[:len(seg_chars)]
    for k, i in enumerate(fill):
        lyrics[i] = seg_chars[k]
    # 记录实际填了几个
    filled = len(fill)
    print(f'{seg_name}(bar{b1}-{b2}): 音符{len(idxs)} 歌词{len(seg_chars)} 填充{filled} R{len(idxs)-filled} (阈值{threshold})')

if problems:
    print('\n!!! 问题:')
    for p in problems:
        print(' ', p)

# ---- 5. 检查未填词的长音 ----
unfilled_long = [i for i, l in enumerate(lyrics) if l == 'R' and notes[i]['dur'] >= 480]
print(f'\n未填词的长音(>=4分): {len(unfilled_long)}')

# ---- 6. 输出 ----
os.makedirs(OUT_DIR, exist_ok=True)

# 6.1 X Studio 歌词 txt（逐行）
txt_path = os.path.join(OUT_DIR, f'{args.track}_xstudio_lyrics.txt')
with open(txt_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lyrics))
print(f'\n[OK] {txt_path}')

# 6.2 拼音版
lyric_map = {c: (p, cv) for c, p, cv in all_lyrics}
py_path = os.path.join(OUT_DIR, f'{args.track}_xstudio_lyrics_pinyin.txt')
with open(py_path, 'w', encoding='utf-8') as f:
    for l in lyrics:
        if l == 'R':
            f.write('R\n')
        else:
            p, cv = lyric_map.get(l, ('?', '?'))
            f.write(f'{l} {p} {cv}\n')
print(f'[OK] {py_path}')

# 6.3 对照表 MD
md_path = os.path.join(OUT_DIR, f'{args.track}_xstudio.md')
with open(md_path, 'w', encoding='utf-8') as f:
    f.write('# 02_主唱 — X Studio 歌词对照表\n\n')
    f.write(f'- 音符总数: {len(notes)}\n')
    f.write(f'- 歌词字数: {sum(1 for l in lyrics if l != "R")}\n')
    f.write(f'- 休止符(R): {sum(1 for l in lyrics if l == "R")}\n\n')
    f.write('| # | 小节.拍 | MIDI音 | 时值 | 歌词 | 拼音 | 音素 |\n')
    f.write('|---|--------|--------|------|------|------|------|\n')
    for i, nn in enumerate(notes):
        bar = nn['tick'] // (tp * 4) + 1
        rem = nn['tick'] % (tp * 4)
        beat = rem // tp + 1
        sub = (rem % tp) // (tp // 4) + 1
        l = lyrics[i]
        p, cv = ('-', '-') if l == 'R' else lyric_map.get(l, ('?', '?'))
        dur = nn['dur'] / tp
        f.write(f'| {i+1} | {bar}.{beat}.{sub} | {nn["note"]} | {dur:.2f} | {l} | {p} | {cv} |\n')
print(f'[OK] {md_path}')

# 统计
r_count = sum(1 for l in lyrics if l == 'R')
print(f'\n总: {n} 音符 / {n - r_count} 歌词 / {r_count} R')
print(f'歌词利用率: {n - r_count}/{len(all_lyrics)}')
