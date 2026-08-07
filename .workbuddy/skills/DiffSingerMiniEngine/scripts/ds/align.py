# -*- coding: utf-8 -*-
"""对齐层: MIDI音符读取 / 歌词线性对齐 / 分段 / 间隙展开 (迁移自 render_yunye_v2.py)

保留资产(已验证正确, 勿改语义):
- 1音符=1字符线性对齐, 段内字符用尽后剩余音符用'-'拖腔, 段外'R'
- BAR_SEGS 小节边界强制切分(防整段超长 vocoder OOM), 段内再按 R/sing 细分
- expand_gaps: 音符间空隙插入间隙R音符, 保证时间轴连续(吃掉空隙会致节奏漂移)
"""
import mido

# 段落小节范围 -> 03_lyrics.json lyric_sections 索引 (bar 从1计)
# 歌曲专属配置: 当前为「走在」; 换歌时改这里或后续做成CLI参数
BAR_SEGS = [
    (5, 12, 1),    # Verse 1
    (13, 20, 2),   # Verse 2
    (21, 24, 3),   # Interlude
    (25, 32, 4),   # Chorus 1
    (33, 40, 5),   # Verse 3
    (41, 47, 6),   # Chorus 2
    (48, 52, 7),   # Outro
]


def read_midi_notes(path):
    """mid -> (notes, TPB); notes: [{tick, note, dur}], 取 track[1](无则track[0])"""
    mid = mido.MidiFile(path)
    tpb = mid.ticks_per_beat
    open_n = {}
    notes = []
    tick = 0
    for msg in (mid.tracks[1] if len(mid.tracks) > 1 else mid.tracks[0]):
        tick += msg.time
        if msg.type == "note_on" and msg.velocity > 0:
            open_n[msg.note] = tick
        elif (msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0)) \
                and msg.note in open_n:
            s = open_n.pop(msg.note)
            notes.append({"tick": s, "note": msg.note, "dur": tick - s})
    return notes, tpb


def extract_section_chars(lines):
    """从段落 lines 提取有效字符(汉字 + '-'/'～' 转音标记), 跳过 … 等装饰符

    '-'/'～' = 显式转音(slur): 前一个汉字韵母延长到该音符(一字多音),
    与 xstudio_lyrics 技能同一约定; 段内字符用尽后剩余音符仍自动补 '-'。
    """
    chars = []
    for line in lines:
        for ch in line:
            if "一" <= ch <= "鿿":
                chars.append(ch)
            elif ch in ("-", "～"):
                chars.append("-")
    return chars


def align_lyrics_linear(midi_notes, sections, bar_segs, tpb):
    """1音符=1字符线性对齐; 段内字符用尽后剩余音符用'-'延续韵母(拖腔); 段外 R"""
    lyrics = ["R"] * len(midi_notes)
    for b1, b2, sec_idx in bar_segs:
        if sec_idx >= len(sections):
            continue
        chars = extract_section_chars(sections[sec_idx].get("lines", []))
        if not chars:
            continue
        idxs = [i for i, n in enumerate(midi_notes)
                if b1 <= n["tick"] // (tpb * 4) + 1 <= b2]
        for k, i in enumerate(idxs):
            lyrics[i] = chars[k] if k < len(chars) else "-"
    return lyrics


def split_segments(notes, lyrics, tpb, bar_segs):
    """先按段落小节边界强制切分(防整段超长 vocoder OOM/质量下降),
    段内再按 R/sing 细分。返回 ('rest'|'sing', start, end) 列表"""
    from bisect import bisect_left
    note_ticks = [n["tick"] for n in notes]
    cuts = {0, len(notes)}
    for b1, b2, _ in bar_segs:
        cuts.add(bisect_left(note_ticks, (b1 - 1) * tpb * 4))
        cuts.add(bisect_left(note_ticks, b2 * tpb * 4))
    cuts = sorted(cuts)
    segs = []
    for ca, cb in zip(cuts, cuts[1:]):
        i = ca
        while i < cb:
            j = i
            if lyrics[i] == "R":
                while j < cb and lyrics[j] == "R":
                    j += 1
                segs.append(("rest", i, j))
            else:
                while j < cb and lyrics[j] != "R":
                    j += 1
                segs.append(("sing", i, j))
            i = j
    return segs


def expand_gaps(notes, lyrics):
    """段内音符之间插入间隙R音符(SP静音), 使序列在时间轴上连续。
    否则附点节奏/呼吸空隙被吃掉, 全曲节奏漂移"""
    out_n, out_l = [], []
    for i, (n, l) in enumerate(zip(notes, lyrics)):
        out_n.append(n)
        out_l.append(l)
        if i + 1 < len(notes):
            gap = notes[i + 1]["tick"] - (n["tick"] + n["dur"])
            if gap > 0:
                out_n.append({"tick": n["tick"] + n["dur"], "note": 0, "dur": gap})
                out_l.append("R")
    return out_n, out_l
