#!/usr/bin/env python3
"""
composer.py - 沙发小曲自动编曲生成器
基于基础和弦进行 + 旋律数据，生成丰富的和弦编曲方案
"""

import re
import json
from dataclasses import dataclass, field, asdict
from typing import Optional


# ============================================================
# 常量定义
# ============================================================

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# 调内和弦映射（C大调）
CHORD_DEGREES = {
    "C":  [0, 4, 7],
    "D":  [2, 6, 9],
    "E":  [4, 8, 11],
    "F":  [5, 9, 12],
    "G":  [7, 11, 14],
    "A":  [9, 13, 16],
    "B":  [11, 15, 18],
    "Cb": [-1, 3, 7],
    "Db": [1, 5, 8],
    "Eb": [3, 7, 10],
    "Fb": [4, 8, 11],
    "Gb": [6, 10, 13],
    "Ab": [8, 12, 15],
    "Bb": [10, 14, 17],
}

# C大调关系小调
MINOR_RELATIVE = {
    "C": "Am", "D": "Bm", "E": "C#m", "F": "Dm",
    "G": "Em", "A": "Bm", "B": "C#m",
}

# 标准和弦后缀
CHORD_SUFFIXES = {
    "maj": [0, 4, 7],       # 大三和弦
    "min": [0, 3, 7],       # 小三和弦
    "7":   [0, 4, 7, 10],   # 属七
    "maj7":[0, 4, 7, 11],   # 大七
    "min7":[0, 3, 7, 10],   # 小七
    "9":   [0, 4, 7, 10, 14],   # 九和弦
    "13":  [0, 4, 7, 10, 14, 21], # 十三和弦
    "sus4":[0, 5, 7],       # 挂四
    "sus2":[0, 2, 7],       # 挂二
    "add9":[0, 4, 7, 14],   # 加九
    "dim": [0, 3, 6],       # 减三
    "aug": [0, 4, 8],       # 增三
    "7sus4":[0, 5, 7, 10],  # 属七挂四
    "6":   [0, 4, 7, 9],    # 六和弦
    "m9":  [0, 3, 7, 10, 14], # 小九
    "m7b5":[0, 3, 6, 10],   # 半减七
    "11":  [0, 3, 7, 10, 14, 17], # 十一声（小调）
    "maj9":[0, 4, 7, 11, 14], # 大九
    "7alt":[0, 4, 7, 10, 13], # 变化属七
}

# 沙发小曲扩展和弦库（在基础骨架上可用的丰富和弦）
SOFA_ENRICH_CHORDS = {
    # 主功能（C7系）
    "Cmaj9":  "x 3 2 0 3 0",
    "Cadd9":  "x 3 2 0 3 3",
    "C7sus4": "x 3 3 3 3 3",
    "C9":     "x 3 2 3 3 3",
    "C13":    "x 3 2 3 3 5",
    "Cmaj7":  "x 3 2 0 0 0",
    # 属七替代（降低张力）
    "C7/E":   "0 3 2 3 3 0",
    # 小七功能（Em7/B系）
    "Em11":   "0 2 4 4 3 0",
    "Em9":    "0 2 4 2 3 0",
    "Emaj9":  "0 2 4 1 3 0",
    # 过渡和弦
    "Am9":    "5 5 7 5 8 5",
    "Am7":    "5 5 7 5 7 5",
    "Fmaj9":  "x 3 2 0 3 0",
    "Gm7":    "3 5 3 3 3 3",
    # 呼吸/预备和弦
    "E7sus4": "0 2 4 4 5 0",
    "E7alt":  "0 2 4 3 5 0",
    "Bm7b5":  "x 2 3 3 3 0",
    "Bm9":    "x 2 3 2 3 0",
    "Fadd9":  "x 3 3 2 3 3",
    # Bass line 专属（低音重要）
    "Em7/B":  "x 2 4 3 3 0",   # 沙发进行核心，低音 B
    "Em9/B":  "x 2 4 2 3 0",
    "Em11/B": "x 2 4 4 3 0",
    "E9/B":   "x 2 4 3 3 0",   # E9 + /B（E 是根音，B 是低音）
    "E11/B":  "x 2 4 4 3 0",
    "Bm9/A":  "x 2 3 2 3 0",
    "Bm7/A":  "x 2 3 3 3 0",
    "C7/E":   "0 3 2 3 3 0",   # C7 转 E
    "C7/B":   "x 2 0 3 3 0",   # C7 转 B（半终止）
    "Em7/A":  "0 2 4 3 0 0",   # Em7 转 A
    "Em9/A":  "0 2 4 2 0 0",
}


# ============================================================
# 数据结构
# ============================================================

@dataclass
class ChordEvent:
    chord: str           # 和弦名（标准格式）
    bar: int             # 小节号（1-based）
    beat: int            # 拍号（1-4）
    guitar_pos: str      # 吉他指法
    note: str            # 备注/说明
    enriched: bool = False  # 是否是丰富后的和弦
    source: str = ""     # 来源：original/enriched/bridge


@dataclass
class MelodyFrame:
    time: float
    note: str
    midi: int
    freq: float
    prob: float


@dataclass
class CompositionResult:
    title: str
    style: str
    tempo: int
    key: str
    form: str
    capo: int = 0          # 夹几品，默认0
    capo_key: str = "C"    # 编配调
    enriched_progression: list = field(default_factory=list)
    section_structure: dict = field(default_factory=dict)
    melody_analysis: dict = field(default_factory=dict)
    guitar_advice: dict = field(default_factory=dict)
    extension_tips: list = field(default_factory=list)


# ============================================================
# 核心函数
# ============================================================

def parse_chord(chord_str: str) -> tuple[str, str, str]:
    """
    解析和弦字符串，返回 (根音, 音名, 后缀)
    例: "Em7/B" -> ("E", "Em7", "/B")
        "C7"    -> ("C", "C7", "")
    """
    chord_str = chord_str.strip()

    # 处理转位标记
    inversion = ""
    if "/" in chord_str and not chord_str.startswith("/"):
        parts = chord_str.rsplit("/", 1)
        if len(parts[1]) <= 3 and not any(c.isdigit() for c in parts[1]):
            chord_str = parts[0]
            inversion = "/" + parts[1]

    # 提取根音（1-2个字符）
    if len(chord_str) >= 2 and chord_str[1] in "#b":
        root = chord_str[:2]
        quality = chord_str[2:]
    else:
        root = chord_str[:1]
        quality = chord_str[1:]

    return root, root + quality, inversion


def midi_to_note_name(midi: int) -> str:
    """MIDI音高转音符名"""
    if midi < 0:
        return "N/A"
    return f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}"


def detect_melody_range(csv_path: str) -> dict:
    """从旋律CSV提取音域统计"""
    import os
    if not os.path.exists(csv_path):
        return {"voiced_frames": 0, "range": "N/A", "avg_note": "N/A", "dominant_notes": []}

    import csv
    notes = []
    midi_vals = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["midi"] and int(row["midi"]) >= 0:
                notes.append(row["note"])
                midi_vals.append(int(row["midi"]))

    if not midi_vals:
        return {"voiced_frames": len(notes), "range": "N/A", "avg_note": "N/A", "dominant_notes": []}

    avg_midi = sum(midi_vals) / len(midi_vals)
    min_midi, max_midi = min(midi_vals), max(midi_vals)

    # 统计出现最多的音符
    note_counts = {}
    for n in notes:
        note_counts[n] = note_counts.get(n, 0) + 1
    dominant = sorted(note_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "voiced_frames": len(notes),
        "range": f"{midi_to_note_name(min_midi)} ~ {midi_to_note_name(max_midi)}",
        "avg_note": midi_to_note_name(int(avg_midi)),
        "avg_midi": avg_midi,
        "dominant_notes": dominant,
        "melody_shape": "稳定巡航" if (max_midi - min_midi) <= 5 else "起伏波动" if (max_midi - min_midi) >= 10 else "微有起伏"
    }


def enrich_chord(chord: str, position: str, bar_num: int) -> tuple[str, str]:
    """
    丰富单个和弦
    position: "start"/"middle"/"end"（在小节中的位置）
    bar_num: 小节号（用于判断段落位置）
    返回: (丰富后和弦名, 吉他指法)
    """
    root, full_name, inv = parse_chord(chord)

    # 属七和弦丰富化（C7系）- 注意排除 m7/maj7/9/13 等
    if full_name.endswith("7") and not full_name.endswith("maj7") and not full_name.endswith("m7") and not full_name.endswith("min7") and not full_name.endswith("97") and not full_name.endswith("sus4") and "m" not in full_name[1:].lower():
        if position == "start":
            # 小节开头用更柔和的替代
            candidates = [f"{root}maj9", f"{root}add9", f"{root}7sus4", f"{root}7/E"]
        elif position == "middle":
            # 中间保持张力，或加挂留
            candidates = [full_name, f"{root}9", f"{root}7sus4"]
        else:
            # 结尾倾向解决或变体
            candidates = [f"{root}maj7", full_name, f"{root}13"]
        choice = candidates[bar_num % len(candidates)]
        pos = SOFA_ENRICH_CHORDS.get(choice, SOFA_ENRICH_CHORDS.get(full_name, "x 3 2 0 0 0"))
        return choice, pos

    # 小七和弦丰富化（Em7系）
    if full_name.endswith("min7") or (full_name.endswith("m7")):
        # 有转位标记时，候选和弦必须保留低音转位
        if inv:  # 例: Em7/B, Bm7/A
            candidates = [
                f"{root}m9",   # Em9/B
                f"{root}m11",  # Em11/B
                f"{root}m7",   # Em7/B
            ]
            choice = candidates[bar_num % len(candidates)]
            # 恢复原始 bass 转位
            final_chord = choice + inv  # E9 + /B = E9/B
            # 查指法（优先含转位的 key）
            pos = SOFA_ENRICH_CHORDS.get(final_chord)  # 查 "E9/B"
            if not pos:
                pos = SOFA_ENRICH_CHORDS.get(choice)   # 查 "E9"
            if not pos:
                pos = guess_guitar_pos(final_chord)     # guess "E9/B"
            return final_chord, pos
        else:
            candidates = [full_name, f"{root}m9", f"{root}11"]
            choice = candidates[bar_num % len(candidates)]
            pos = SOFA_ENRICH_CHORDS.get(choice, SOFA_ENRICH_CHORDS.get(full_name, "0 2 4 3 0 0"))
            return choice, pos

    # 大三和弦
    if full_name.endswith("maj") or (full_name[1:] in ["", "m", "maj"]):
        if full_name.endswith("maj7"):
            candidates = [full_name, f"{root}maj9", f"{root}6"]
        else:
            candidates = [full_name, f"{root}add9", f"{root}6", f"{root}maj7"]
        choice = candidates[bar_num % len(candidates)]
        pos = SOFA_ENRICH_CHORDS.get(choice, "x 3 2 0 0 0")
        return choice, pos

    # 默认：返回原始
    pos = SOFA_ENRICH_CHORDS.get(full_name, "x 3 2 0 0 0")
    return full_name, pos


def enrich_progression(basic_progression: list, enrichment_level: str = "rich") -> list[dict]:
    """
    丰富化和弦进行

    basic_progression: 基础和弦列表，如 ["C7", "C7", "Em7/B", "Em7/B", "Em7"]
    enrichment_level: "light" / "rich" / "full"（丰富程度）

    返回: 展开的小节级和弦列表，每项含 bar, chord, enriched, guitar_pos, note
    """
    result = []
    bar_num = 1

    # 检测循环单元长度（找重复模式）
    cycle_len = detect_cycle_len(basic_progression)

    for i, chord in enumerate(basic_progression):
        cycle_pos = i % cycle_len
        is_cycle_start = (cycle_pos == 0)
        is_cycle_end = (cycle_pos == cycle_len - 1)

        # 根据位置决定是否丰富
        if is_cycle_start and enrichment_level in ("rich", "full"):
            enriched, pos = enrich_chord(chord, "start", bar_num)
        elif is_cycle_end:
            enriched, pos = enrich_chord(chord, "end", bar_num)
        elif cycle_pos == 1 and enrichment_level == "full":
            enriched, pos = enrich_chord(chord, "middle", bar_num)
        else:
            enriched, pos = enrich_chord(chord, "middle", bar_num)
            # enrich_chord 已经返回了正确的指法（可能是 guess），不要覆盖
            # 但如果原始 chord 在 SOFA_ENRICH_CHORDS 有更准确的指法，则用那个
            if chord in SOFA_ENRICH_CHORDS:
                # 指法用 SOFA_ENRICH_CHORDS 里的精确值（包含转位）
                # 但保留 enrich_chord 返回的和弦名（可能已丰富）
                pos = SOFA_ENRICH_CHORDS[chord]

        # 生成备注
        note = ""
        if enriched != chord:
            note = f"丰富自 {chord}"
        if is_cycle_end and chord == basic_progression[-1]:
            note = "（段落收束）" + note

        result.append({
            "bar": bar_num,
            "chord": enriched,
            "guitar_pos": pos,
            "original": chord if enriched != chord else None,
            "enriched": enriched != chord,
            "note": note,
        })
        bar_num += 1

    return result


def transpose_note(note_name: str, semitones: int) -> str:
    """将一个音符向上平移 N 个半音，返回新的音符名（优先用 flat 记谱）"""
    if semitones == 0:
        return note_name
    chroma_map = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3,
                  "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8,
                  "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}
    # 吉他手习惯用 flats：Eb, Ab, Bb, Db (不是 D#, G#, A#, C#)
    flat_map = {1: "Db", 3: "Eb", 6: "Gb", 8: "Ab", 10: "Bb"}
    root = note_name.rstrip("0123456789#b")
    if root not in chroma_map:
        return note_name
    new_chroma = (chroma_map[root] + semitones) % 12
    suffix = note_name[len(root):]
    new_root = flat_map.get(new_chroma, NOTE_NAMES[new_chroma])
    return new_root + suffix


def detect_cycle_len(progression: list) -> int:
    """检测和弦进行的循环单元长度"""
    n = len(progression)
    for length in range(1, n + 1):
        # 检查是否整除
        if n % length != 0:
            continue
        cycle = progression[:length]
        is_repeating = True
        for i in range(length, n, length):
            chunk = progression[i:i + length]
            if chunk != cycle:
                is_repeating = False
                break
        if is_repeating:
            return length
    return n


def guess_guitar_pos(chord: str) -> str:
    """猜测吉他指法（基于标准开放和弦）"""
    root, full, inv = parse_chord(chord)
    chord_lower = full.lower()

    common_pos = {
        "c": "x 3 2 0 3 0",
        "d": "x x 0 2 3 2",
        "dm": "x x 0 2 3 1",
        "e": "0 2 2 1 0 0",
        "em": "0 2 2 0 0 0",
        "f": "1 3 3 2 1 1",
        "g": "3 2 0 0 0 3",
        "am": "x 0 2 2 1 0",
        "a": "x 0 2 2 2 0",
        "bm": "x 2 4 4 3 2",
        "b": "x 2 4 4 4 2",
    }

    base = chord_lower.replace("7", "").replace("maj", "").replace("min", "m").replace("sus4", "sus4").replace("sus2", "sus2")
    if base in common_pos:
        return common_pos[base]
    return "x 3 2 0 0 0"  # 默认 C 把位


def generate_section_structure(tempo: int, form: str = "standard") -> dict:
    """
    生成段落结构

    form: "standard"（沙发核）/ "bloom"（沙发绽）/ "custom"
    """
    structures = {
        "standard": {
            "name": "沙发核（基础形态）",
            "description": "纯吉他+人声，全程慵懒平缓",
            "sections": [
                {"name": "前奏", "bars": 4, "instrument": "纯吉他沙发进行", "energy": 1},
                {"name": "主歌 A", "bars": 8, "instrument": "吉他+人声", "energy": 1.2},
                {"name": "主歌 B", "bars": 8, "instrument": "吉他+人声", "energy": 1.4},
                {"name": "间奏", "bars": 4, "instrument": "吉他独奏/旋律加花", "energy": 1.5},
                {"name": "主歌 A'", "bars": 8, "instrument": "吉他+人声", "energy": 1.2},
                {"name": "尾奏", "bars": 4, "instrument": "吉他弱化", "energy": 0.5},
            ],
            "total_bars": 36,
            "total_seconds": round(36 * 4 * 60 / tempo, 1),
        },
        "bloom": {
            "name": "沙发绽（延伸形态）",
            "description": "从沙发核自然舒展，融入其他乐器",
            "sections": [
                {"name": "前奏", "bars": 4, "instrument": "纯吉他沙发核质感", "energy": 1},
                {"name": "主歌", "bars": 8, "instrument": "吉他+人声，基础形态", "energy": 1.2},
                {"name": "预副歌", "bars": 4, "instrument": "极弱加入贝斯/沙锤", "energy": 1.5},
                {"name": "副歌", "bars": 8, "instrument": "全部延伸乐器进入", "energy": 2.0},
                {"name": "间奏", "bars": 4, "instrument": "乐器 Solo（吉他/口琴）", "energy": 1.8},
                {"name": "主歌+副歌", "bars": 8, "instrument": "反复", "energy": 1.5},
                {"name": "尾奏", "bars": 4, "instrument": "乐器逐层褪去 → 纯吉他", "energy": 0.5},
            ],
            "total_bars": 40,
            "total_seconds": round(40 * 4 * 60 / tempo, 1),
        },
    }
    return structures.get(form, structures["standard"])


def analyze_melody_for_chords(melody_csv_path: str) -> dict:
    """基于旋律分析，推荐和弦落点"""
    analysis = detect_melody_range(melody_csv_path)
    if analysis["voiced_frames"] == 0:
        return {"status": "no_melody_data", "tips": ["请提供音频文件以分析旋律"]}

    tips = []

    # 音域分析
    if analysis["melody_shape"] == "稳定巡航":
        tips.append("旋律以稳定音为主，适合用挂留和弦增加慵懒感")
        tips.append("可在小节中间插入 sus4，和弦转换不必太频繁")
    elif analysis["melody_shape"] == "起伏波动":
        tips.append("旋律有较大起伏，可在高潮处使用 C9/C13 增加张力")
        tips.append("低音区域（G2-G3）适合小七和弦，高音区域适合大七或 add9")

    # 主导音分析
    if analysis["dominant_notes"]:
        top_note = analysis["dominant_notes"][0][0]
        note_name = top_note[:-1] if top_note[-1].isdigit() else top_note
        tips.append(f"主导音是 {top_note}，和声应围绕 {note_name} 调性展开")

    return {
        "status": "analyzed",
        "melody_analysis": analysis,
        "chord_tips": tips,
        "suggested_key": "C大调" if analysis["avg_midi"] < 60 else "需要根据实际旋律调整",
    }


def generate_output(
    title: str,
    basic_progression: list,
    melody_csv_path: str = None,
    enrichment: str = "rich",
    form: str = "standard",
    tempo: int = 68,
    capo: int = 0,
    capo_key: str = "C",
) -> CompositionResult:
    """生成完整编曲方案"""

    # 丰富和弦进行
    enriched_bars = enrich_progression(basic_progression, enrichment)

    # 分析旋律
    melody_info = analyze_melody_for_chords(melody_csv_path) if melody_csv_path else {}

    # 段落结构
    structure = generate_section_structure(tempo, form)

    # 吉他建议
    guitar_advice = {
        "right_hand": "拇指低音 + 三指分解，节奏平缓",
        "left_hand": "避免大横按，多用开放把位或转位",
        "dynamics": f"BPM {tempo}，全程匀速，极轻微 shuffle",
        "texture": "分解为主，扫弦仅限极轻空心扫",
    }

    # 延伸建议
    extension_tips = [
        "L1 轻绽: 加入沙锤（每小节第 2、4 拍轻点）",
        "L2 舒展: 加入 upright bass（拨弦，弱拍进入）+ 口琴旋律线",
        "L3 漫放: 加入轻柔电钢琴和声垫音 + 低保真鼓机（808弱音色）",
    ]

    # Capo 移调计算实际调
    actual_key = transpose_note(capo_key.replace("大调", "").replace("小调", ""), capo) + ("大调" if "小调" not in capo_key else "小调")
    if "大调" not in actual_key and "小调" not in actual_key:
        actual_key = actual_key + "大调"

    return CompositionResult(
        title=title,
        style="沙发小曲",
        tempo=tempo,
        key=actual_key,
        form=structure["name"],
        capo=capo,
        capo_key=capo_key,
        enriched_progression=enriched_bars,
        section_structure=structure,
        melody_analysis=melody_info,
        guitar_advice=guitar_advice,
        extension_tips=extension_tips,
    )


def format_markdown(result: CompositionResult) -> str:
    """格式化为 Markdown 输出"""
    lines = []

    lines.append(f"# 《{result.title}》— 沙发小曲编曲方案")
    lines.append("")
    lines.append("## 风格定位")
    lines.append(f"- **形态**: {result.form}")
    lines.append(f"- **风格**: {result.style}")
    lines.append(f"- **BPM**: {result.tempo}")
    lines.append(f"- **调号**: {result.key}")
    lines.append("")

    # 基础信息（Capo）
    if result.capo > 0:
        actual_key = transpose_note(result.capo_key, result.capo)
        lines.append("## 基础信息")
        lines.append(f"- **Capo**: {result.capo}（夹{result.capo}品）")
        lines.append(f"- **编配调**: {result.capo_key}（吉他指法基于此调）")
        lines.append(f"- **实际音高**: {actual_key}（Capo {result.capo} 后弹出的调）")
        lines.append(f"- **弹法**: {result.capo_key} 编配")
        lines.append("")
    else:
        lines.append("## 基础信息")
        lines.append(f"- **弹法**: {result.capo_key} 编配，无 Capo")
        lines.append("")

    # 和弦进行
    lines.append("## 和弦进行")
    lines.append("")
    lines.append(f"**基础进行**: `{' → '.join(e['original'] if e['original'] else e['chord'] for e in result.enriched_progression)}`")
    lines.append("")

    lines.append("### 丰富化展开")
    lines.append("")
    lines.append("| 小节 | 和弦 | 吉他指法 | 备注 |")
    lines.append("|------|------|---------|------|")
    for bar in result.enriched_progression:
        note = bar["note"] or ("原始" if not bar["enriched"] else "")
        lines.append(f"| {bar['bar']} | {bar['chord']} | `{bar['guitar_pos']}` | {note} |")
    lines.append("")

    # 段落结构
    lines.append("## 段落结构")
    lines.append("")
    lines.append(f"**总时长**: 约 {result.section_structure['total_seconds']:.0f} 秒（{result.section_structure['total_bars']} 小节）")
    lines.append(f"**结构描述**: {result.section_structure['description']}")
    lines.append("")

    # 结构图
    arrow = " → "
    section_flow = arrow.join(s["name"] for s in result.section_structure["sections"])
    lines.append("```")
    lines.append(section_flow)
    lines.append("```")
    lines.append("")

    lines.append("### 各段落详情")
    lines.append("")
    for sec in result.section_structure["sections"]:
        lines.append(f"#### {sec['name']}（{sec['bars']}小节）")
        lines.append(f"- 乐器: {sec['instrument']}")
        energy_bars = int(sec['energy'])
        if sec['energy'] >= 1:
            lines.append(f"- 能量感: 🪶 {'░' * max(0, energy_bars - 1)}")
        else:
            lines.append("- 能量感: ○○○")
        lines.append("")

    # 旋律分析
    if result.melody_analysis and result.melody_analysis.get("status") == "analyzed":
        ma = result.melody_analysis["melody_analysis"]
        lines.append("## 旋律分析与和弦落点建议")
        lines.append("")
        lines.append(f"- **音域**: {ma['range']}")
        lines.append(f"- **主导音**: {ma['dominant_notes'][0][0] if ma.get('dominant_notes') else 'N/A'}")
        lines.append(f"- **旋律形态**: {ma['melody_shape']}")
        lines.append("")
        lines.append("**和弦落点建议:**")
        for tip in result.melody_analysis.get("chord_tips", []):
            lines.append(f"- {tip}")
        lines.append("")
    elif result.melody_analysis.get("status") == "no_melody_data":
        lines.append("## 旋律分析")
        lines.append("⚠️ 未提供旋律数据，和弦进行基于基础骨架设计。")
        lines.append("如提供音频文件（@音频文件），可结合旋律走向优化落点。")
        lines.append("")

    # 吉他建议
    lines.append("## 吉他编法建议")
    lines.append("")
    lines.append(f"- **右手**: {result.guitar_advice['right_hand']}")
    lines.append(f"- **左手**: {result.guitar_advice['left_hand']}")
    lines.append(f"- **力度**: {result.guitar_advice['dynamics']}")
    lines.append(f"- **音色**: {result.guitar_advice['texture']}")
    lines.append("")
    lines.append("### 核心把位速查")
    lines.append("")
    lines.append("```")
    for chord, pos in list(SOFA_ENRICH_CHORDS.items())[:12]:
        lines.append(f"{chord:<8} {pos}")
    lines.append("```")
    lines.append("")

    # 延伸建议
    if "bloom" in result.form.lower():
        lines.append("## 延伸升级路径（沙发绽）")
        lines.append("")
        for tip in result.extension_tips:
            lines.append(f"- {tip}")
        lines.append("")

    # 页脚
    lines.append("---")
    lines.append("*由 ai_chords_master 生成 | 基于沙发小曲风格体系*")

    return "\n".join(lines)


# ============================================================
# CLI 入口
# ============================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="沙发小曲自动编曲生成器")
    parser.add_argument("--title", default="未命名沙发曲", help="歌曲名")
    parser.add_argument("--progression", required=True, help="基础和弦进行，逗号分隔，如 'C7,C7,Em7/B,Em7/B,Em7'")
    parser.add_argument("--melody", default=None, help="旋律 CSV 文件路径")
    parser.add_argument("--enrichment", default="rich", choices=["light", "rich", "full"], help="丰富程度")
    parser.add_argument("--form", default="standard", choices=["standard", "bloom"], help="曲式形态")
    parser.add_argument("--tempo", type=int, default=68, help="BPM")
    parser.add_argument("--capo", type=int, default=0, help="夹几品（默认0）")
    parser.add_argument("--capo-key", default="C", help="编配调（默认C）")
    parser.add_argument("-o", "--output", default=None, help="输出文件路径")

    args = parser.parse_args()

    # 解析和弦进行
    progression = [c.strip() for c in args.progression.split(",") if c.strip()]

    # 生成
    result = generate_output(
        title=args.title,
        basic_progression=progression,
        melody_csv_path=args.melody,
        enrichment=args.enrichment,
        form=args.form,
        tempo=args.tempo,
        capo=args.capo,
        capo_key=args.capo_key,
    )

    # 输出
    output = format_markdown(result)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"✅ 编曲方案已生成: {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
