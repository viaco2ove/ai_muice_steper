# -*- coding: utf-8 -*-
"""
ust_generator.py - 把 song_engineer 主唱数据转成 OpenUTAU .ust 文件

读: workspace/project/走在/song_engineer/track/02_主唱.md (含逐字表)
输出: workspace/project/走在/song_engineer/track/02_主唱.ust

策略:
  1. 解析 md 中的"逐字表", 提取 (字, 音名, 时值, 拍位, 力度)
  2. 表头必须第一列=字, 其它列(句序/歌词/起音/落音)跳过
  3. 副歌重复段第 1-3 组缺失, 自动复制第一段副歌(力度递减 mp->p->pp)
  4. 直接用 md 表的 (字|音名|时值|拍位|力度) 生成 UST,不依赖 MIDI
"""
import os
import re


MD = "workspace/project/走在/song_engineer/track/02_主唱.md"
OUT_UST = "workspace/project/走在/song_engineer/track/02_主唱.ust"
OUT_INSPECT = "workspace/project/走在/song_engineer/track/02_主唱.inspect.txt"

TICKS_PER_BEAT = 480
TICKS_PER_BAR = TICKS_PER_BEAT * 4  # 1920


def parse_md_words(md_path):
    """解析 02_主唱.md 的逐字表"""
    text = open(md_path, encoding="utf-8").read()
    lines = text.split("\n")

    words = []
    current_section = None
    # 段落标题识别: "### 副歌重复 [Chorus]" -> 用 "副歌重复" 标题作为标识
    section_re = re.compile(r"^###\s+(.+?)\s*\[(.+?)\]")
    chorus_count = 0  # 用于区分第 1 段副歌 / 第 2 段副歌

    in_table = False
    is_word_table = False

    for line in lines:
        m = section_re.match(line.strip())
        if m:
            label = m.group(1).strip()
            tag = m.group(2).strip()
            # 把多个相同 tag 区分开
            if tag == "Chorus":
                chorus_count += 1
                # 第 1 段副歌保持 "Chorus", 第 2 段副歌改名 "Chorus 2"
                if chorus_count >= 2:
                    tag = f"Chorus {chorus_count}"
            current_section = tag
            in_table = False
            is_word_table = False
            continue
        if line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 5:
                first = cells[0]
                if first == "字" and "音名" in cells[1]:
                    in_table = True
                    is_word_table = True
                    continue
                elif first in ("句序", "歌词", "组"):
                    in_table = True
                    is_word_table = False
                    continue
        if in_table and line.strip().startswith("|---"):
            continue
        if in_table and is_word_table and line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 5:
                continue
            char = cells[0]
            note = cells[1]
            duration = cells[2]
            beat_pos = cells[3]
            dyn = cells[4]
            is_rest = "(气口)" in char or note == "-" or beat_pos == "-"
            words.append({
                "section": current_section,
                "char": char.replace("*(气口)*", "").replace("(气口)", ""),
                "is_rest": is_rest,
                "note_name": note,
                "duration": duration,
                "beat_pos": beat_pos,
                "dyn": dyn,
            })
        elif line.strip() == "":
            in_table = False
            is_word_table = False

    # 副歌重复前 3 组补全: 找到 "Chorus" 段和 "Chorus 2" 段之间的差
    chorus_idx = None
    chorus2_idx = None
    for i, w in enumerate(words):
        if w["section"] == "Chorus" and chorus_idx is None:
            chorus_idx = i
        elif w["section"].startswith("Chorus ") and chorus2_idx is None:
            chorus2_idx = i
    if chorus_idx is not None and chorus2_idx is not None:
        first_chorus = words[chorus_idx:chorus2_idx]
        # 第一段副歌分 4 组(8 音符/组)
        chorus_groups = [first_chorus[i:i + 8] for i in range(0, len(first_chorus), 8)]
        prefix = []
        for gi in range(min(3, len(chorus_groups))):
            dyn = ["mp", "p", "pp"][gi]
            for w in chorus_groups[gi]:
                nw = dict(w)
                nw["dyn"] = dyn
                nw["section"] = "Chorus 2"  # 复制部分也归到 Chorus 2 段
                prefix.append(nw)
        # beat_pos 也要调整到 41-46 (粗略 +24 bar)
        for j, w in enumerate(prefix):
            old = w["beat_pos"]
            mm = re.match(r"(\d+)\.(\d+)\.(\d+)", old)
            if mm:
                bar = int(mm.group(1))
                w["beat_pos"] = f"{bar + 24}.{mm.group(2)}.{mm.group(3)}"
        words = words[:chorus2_idx] + prefix + words[chorus2_idx:]

    return words


def note_name_to_midi(name):
    if not name or name == "-":
        return None
    m = re.match(r"([A-G])([#b]?)(-?\d+)", name.strip())
    if not m:
        return None
    letter, accidental, octave = m.group(1), m.group(2), m.group(3)
    base = {"C":0,"D":2,"E":4,"F":5,"G":7,"A":9,"B":11}[letter]
    if accidental == "#":
        base += 1
    elif accidental == "b":
        base -= 1
    return base + (int(octave) + 1) * 12


def dyn_to_intensity(dyn):
    m = {"ppp": 30, "pp": 45, "p": 60, "mp": 75, "mf": 85, "f": 95}
    return m.get(dyn, 60)


def duration_to_ticks(dur_str):
    s = dur_str
    for k, v in [("全延", 1920), ("全分", 1920), ("2分", 960),
                 ("4分", 480), ("8分", 240), ("16分", 120)]:
        if k in s:
            return v
    return 480


def beat_pos_to_bar(beat_pos):
    """beat_pos '5.1.1' -> 5"""
    if not beat_pos or beat_pos == "-":
        return 0
    return int(beat_pos.split(".")[0])


def write_ust(words, out_path):
    lines = []
    lines.append("[#VERSION]")
    lines.append("UST Version 2.0")
    lines.append("[#SETTING]")
    lines.append("Tempo=68.00")
    lines.append("Tracks=1")
    lines.append("ProjectName=走在-主唱")
    lines.append("VoiceDir=")
    lines.append("OutFile=02_主唱.wav")
    lines.append("CacheDir=")
    lines.append("Mode2=True")

    last_section = None
    for i, w in enumerate(words):
        section = w["section"]
        if section != last_section:
            lines.append(f"; === {section} ===")
            lines.append(f"MARKBEGIN={section.replace(' ', '_')}")
            last_section = section

        if w["is_rest"]:
            lyric = "R"
            note_num = "0"
            intensity = 0
        else:
            md_midi = note_name_to_midi(w["note_name"])
            if md_midi is None:
                md_midi = 60
            lyric = w["char"]
            note_num = str(md_midi)
            intensity = dyn_to_intensity(w["dyn"])

        length = duration_to_ticks(w["duration"])

        idx = str(i).zfill(4)
        lines.append(f"[#{idx}]")
        lines.append(f"Length={length}")
        lines.append(f"NoteNum={note_num}")
        lines.append(f"Lyric={lyric}")
        lines.append(f"Intensity={intensity}")
        lines.append(f"Velocity={intensity}")
        lines.append(f"Modulation=0")
        lines.append(f"PBType=5")
        lines.append(f"PBW=0")
        lines.append(f"PBS=0")
        lines.append(f"PBY=0")
        lines.append(f"Flags=")
        lines.append(f"PreUtter=")
        lines.append(f"VoiceOverlap=")

    lines.append("[#TRACKEND]")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    if not os.path.exists(MD):
        print(f"[错误] 缺 {MD}")
        return

    words = parse_md_words(MD)
    rests = sum(1 for w in words if w["is_rest"])
    chars = sum(1 for w in words if not w["is_rest"])

    print("=== ust_generator ===")
    print(f"md 逐字表: {len(words)} 项 (字 {chars} + 气口 {rests})")
    sections = []
    for w in words:
        if not sections or sections[-1] != w["section"]:
            sections.append(w["section"])
    print(f"段落顺序: {sections}")

    write_ust(words, OUT_UST)
    print(f"[输出] {OUT_UST}")
    print(f"  音符块: {len(words)}")

    # 写对照清单
    with open(OUT_INSPECT, "w", encoding="utf-8") as f:
        f.write(f"# 02_主唱.md -> .ust 对照\n\n")
        f.write(f"总项: {len(words)} | 字: {chars} | 气口: {rests}\n")
        f.write(f"段落: {sections}\n\n")
        f.write("| # | 段落 | bar | 字/气 | 音名 | MIDI | ticks | 力度 |\n")
        f.write("|---|------|-----|------|------|------|-------|------|\n")
        for i, w in enumerate(words):
            midi = note_name_to_midi(w["note_name"]) if w["note_name"] != "-" else "-"
            f.write(f"| {i} | {w['section']} | {beat_pos_to_bar(w['beat_pos'])} | "
                    f"{w['char']} | {w['note_name']} | {midi} | "
                    f"{duration_to_ticks(w['duration'])} | {w['dyn']} |\n")
    print(f"[清单] {OUT_INSPECT}")

    # UST 文件前 30 行预览
    print(f"\n.ust 文件头 30 行:")
    with open(OUT_UST, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= 30:
                break
            print(f"  {line.rstrip()}")


if __name__ == "__main__":
    main()