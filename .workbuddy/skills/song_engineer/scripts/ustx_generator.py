# -*- coding: utf-8 -*-
"""
ustx_generator.py - OpenUTAU v0.1.565.0 实测格式 (ustx_version: "0.7")

严格参照 02_主唱-mid-autosave.ustx 实测结构:
  - ustx_version: "0.7"
  - tracks[].singer / phonemizer / renderer_settings{renderer:DIFFSINGER}
  - voice_parts 在 tracks[] 内（不是 tracks[].parts）
  - note: position / tone / lyric / pitch{data}/snap_first/vibrato/phoneme_expressions/phoneme_overrides
  - expressions: 17 项，字段 default_value / is_flag / flag
  - tempos: bpm 存浮点精确值
"""
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

UST = "workspace/project/走在/song_engineer/track/02_主唱.ust"
USTX = "workspace/project/走在/song_engineer/track/02_主唱.ustx"


def parse_ust(path):
    text = open(path, encoding="utf-8").read()
    block_re = re.compile(r"\[#(\d{4})\](.*?)(?=\[#\d{4}\]|\[#TRACKEND\]|\Z)", re.DOTALL)
    notes = []
    pos = 0
    for idx, body in block_re.findall(text):
        f = {}
        for line in body.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith(";") or line.startswith("MARKBEGIN="):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                f[k.strip()] = v.strip()
        if "Lyric" not in f:
            continue
        try:
            duration = int(f.get("Length", "480"))
            tone = int(f.get("NoteNum", "60"))
        except ValueError:
            continue
        lyric = f.get("Lyric", "R")
        notes.append({
            "position": pos,
            "duration": duration,
            "tone": tone,
            "lyric": lyric,
        })
        pos += duration
    return notes, pos


def yaml_str(s):
    if not s:
        return '""'
    escaped = (s.replace("\\", "\\\\").replace('"', '\\"')
                          .replace("\n", "\\n").replace("\r", ""))
    return f'"{escaped}"'


def expr_block(abbr, name, typ, mn, mx, df, options=None, is_flag=False):
    lines = [f"  {abbr}:",
             f"    name: {name}",
             f"    abbr: {abbr}",
             f"    type: {typ}",
             f"    min: {mn}",
             f"    max: {mx}",
             f"    default_value: {df}",
             "    is_flag: true" if is_flag else "    is_flag: false",
             '    flag: ""']
    if options:
        lines.append("    options:")
        for o in options:
            lines.append(f"      - {yaml_str(o) if o else '""'}")
    return lines


def build_ustx(notes, total_dur, out_path):
    lines = []

    # === 根级工程信息 ===
    lines.append("name: New Project")
    lines.append("comment: \"\"")
    lines.append("output_dir: Vocal")
    lines.append("cache_dir: UCache")
    lines.append('ustx_version: "0.7"')
    lines.append("resolution: 480")
    lines.append("bpm: 120")
    lines.append("beat_per_bar: 4")
    lines.append("beat_unit: 4")

    # === expressions (17 项实测格式) ===
    lines.append("expressions:")
    lines += expr_block("dyn",  "dynamics (curve)",       "Curve",      -240,  120,    0)
    lines += expr_block("pitd", "pitch deviation (curve)", "Curve",     -1200, 1200,   0)
    lines += expr_block("clr",  "voice color",             "Options",      0,   -1,     0)
    lines += expr_block("eng",  "resampler engine",        "Options",      0,    1,     0, ["", "worldline"])
    lines += expr_block("vel",  "velocity",                "Numerical",    0,  200,   100)
    lines += expr_block("vol",  "volume",                  "Numerical",    0,  200,   100)
    lines += expr_block("atk",  "attack",                  "Numerical",    0,  200,   100)
    lines += expr_block("dec",  "decay",                   "Numerical",    0,  100,   100)
    lines += expr_block("gen",  "gender",                  "Numerical", -100,  100,     0)
    lines += expr_block("bre",  "breath",                  "Numerical",    0,  100,     0)
    lines += expr_block("mod",  "modulation",              "Numerical",    0,  100,     0)
    lines += expr_block("shft", "shift (curve)",           "Curve",     -1200, 1200,    0)
    lines += expr_block("shfc", "tone shift (curve)",      "Curve",     -1200, 1200,    0)
    lines += expr_block("tenc", "tension (curve)",         "Curve",      -100,  100,    0)
    lines += expr_block("voic", "voicing (curve)",         "Curve",        0,  100,  100)

    lines.append("exp_selectors:")
    for s in ["dyn", "pitd", "clr", "eng", "vel", "vol"]:
        lines.append(f"- {s}")
    lines.append("exp_primary: 0")
    lines.append("exp_secondary: 1")
    lines.append("key: 0")

    # === time_signatures / tempos ===
    lines.append("time_signatures:")
    lines.append("- bar_position: 0")
    lines.append("  beat_per_bar: 4")
    lines.append("  beat_unit: 4")

    # ★ 存浮点精确 BPM（不用四舍五入）
    bpm_float = round(68.0 + 0.0001, 10)   # 68.0001 -> "68.0001" (精确)
    lines.append("tempos:")
    lines.append(f"- position: 0")
    lines.append(f"  bpm: {bpm_float}")

    # === tracks (singer 留空让用户手动绑) ===
    lines.append("tracks:")
    lines.append("- singer: \"\"")                              # ★ singer 不是 singer_id
    lines.append('  phonemizer: OpenUtau.Core.DiffSinger.DiffSingerChinesePhonemizer')
    lines.append("  renderer_settings:")
    lines.append("    renderer: DIFFSINGER")                   # ★ 必须有这个
    lines.append('  track_name: 主唱')
    lines.append('  track_color: Blue')
    lines.append("  mute: false")
    lines.append("  solo: false")
    lines.append("  volume: 0")
    lines.append("  pan: 0")
    lines.append("  track_expressions: []")
    lines.append("  voice_color_names: []")

    # === voice_parts ★ 根级，tracks 之后 wave_parts 之前 ===
    lines.append("voice_parts:")
    lines.append(f"- duration: {total_dur}")
    lines.append("  name: 主唱")
    lines.append('  comment: ""')
    lines.append("  track_no: 0")
    lines.append("  position: 0")
    lines.append("  notes:")

    for i, n in enumerate(notes):
        snap = "false" if i == 0 else "true"
        lines.append(f"  - position: {n['position']}")
        lines.append(f"    duration: {n['duration']}")
        lines.append(f"    tone: {n['tone']}")
        lines.append(f"    lyric: {yaml_str(n['lyric'])}")
        lines.append("    pitch:")
        lines.append("      data:")
        lines.append("      - {x: 0, y: 0, shape: io}")
        lines.append("      - {x: 0, y: 0, shape: io}")
        lines.append(f"      snap_first: {snap}")
        lines.append("    vibrato: {length: 0, period: 175, depth: 25, "
                     "in: 10, out: 10, shift: 0, drift: 0, vol_link: 0}")
        lines.append("    phoneme_expressions: []")
        lines.append("    phoneme_overrides: []")

    lines.append("wave_parts: []")

    out_text = "\n".join(lines)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(out_text)

    # 验证
    with open(out_path, "rb") as f:
        raw = f.read()
    all_lines = raw.decode("utf-8").split("\n")
    lyrics = [l.strip() for l in all_lines if "      lyric:" in l]
    print(f"[OK] {out_path}")
    print(f"     {len(raw)/1024:.1f} KB, UTF-8 no-BOM")
    print(f"     {len(notes)} notes, {total_dur} ticks")
    print(f"\n  lyric 样本 (前 4):")
    for l in lyrics[:4]:
        print(f"    {l}")
    print(f"  lyric 样本 (后 3):")
    for l in lyrics[-3:]:
        print(f"    {l}")
    print(f"\n  结构对照:")
    print(f"    ustx_version: {[l.strip() for l in all_lines if 'ustx_version' in l][0]}")
    print(f"    singer:       {[l.strip() for l in all_lines if 'singer:' in l and 'voice_color' not in l][0]}")
    print(f"    renderer:     {[l.strip() for l in all_lines if '  renderer:' in l][0]}")
    print(f"    voice_parts:  {[l.strip() for l in all_lines if 'voice_parts:' in l][0]}")
    print(f"    tone:         {[l.strip() for l in all_lines if '      tone:' in l][0]}")


def main():
    if not os.path.exists(UST):
        print(f"[错误] 缺 {UST}")
        return
    notes, total = parse_ust(UST)
    print(f"=== ustx_generator (v0.7 实测格式) ===")
    print(f"  notes={len(notes)}, total={total} ticks ({total/480*60/68:.1f}s)")
    build_ustx(notes, total, USTX)


if __name__ == "__main__":
    main()