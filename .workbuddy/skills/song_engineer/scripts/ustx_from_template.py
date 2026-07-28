# -*- coding: utf-8 -*-
"""
ustx_from_template.py - 用 ruamel.yaml 操作 02_主唱-mid.ustx 模板

严格按官方 spec:
  - ustx_version: "0.6"
  - bpm/beat_per_bar/beat_unit/comment/output_dir/cache_dir 是废弃字段(模板有就保留)
  - renderer_settings 不在 spec 里(但模板有DiffSinger版,保留)
  - voice_parts 在根级, notes[] 在 voice_parts 内
  - note: position/duration/tone/lyric/pitch/vibrato/phoneme_expressions/phoneme_overrides
  - 必须用 ruamel.yaml
"""
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from ruamel.yaml import YAML

TEMPLATE = "workspace/project/走在/song_engineer/track/02_主唱-mid.ustx"
UST = "workspace/project/走在/song_engineer/track/02_主唱.ust"
OUT = "workspace/project/走在/song_engineer/track/02_主唱.ustx"


def parse_ust(path):
    """解析 .ust → note 列表"""
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


def main():
    if not os.path.exists(TEMPLATE):
        print(f"[错误] 缺模板 {TEMPLATE}")
        return
    if not os.path.exists(UST):
        print(f"[错误] 缺 {UST}")
        return

    # 1. 解析 .ust 得到 note 数据
    notes, total_dur = parse_ust(UST)
    print(f"读 .ust: {len(notes)} notes, {total_dur} ticks ({total_dur/480*60/68:.1f}s)")

    # 2. 用 ruamel.yaml 加载模板
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.default_flow_style = False

    with open(TEMPLATE, encoding="utf-8") as f:
        proj = yaml.load(f)

    # 3. 查看模板结构
    print(f"\n模板结构:")
    print(f"  ustx_version: {proj.get('ustx_version')}")
    print(f"  bpm:          {proj.get('bpm')}")
    print(f"  tracks 数:    {len(proj.get('tracks', []))}")
    print(f"  voice_parts 数: {len(proj.get('voice_parts', []))}")
    if proj.get('voice_parts'):
        vp = proj['voice_parts'][0]
        print(f"  voice_parts[0].duration: {vp.get('duration')}")
        print(f"  voice_parts[0].notes 数: {len(vp.get('notes', []))}")

    # 4. 替换 voice_parts[0] 的 notes
    vp = proj['voice_parts'][0]
    vp['duration'] = total_dur

    # 逐个替换 note
    yaml_notes = vp['notes']
    for i, n in enumerate(notes):
        if i < len(yaml_notes):
            note = yaml_notes[i]
        else:
            # 多出来的 note，从模板最后一条复制（保持格式）
            note = dict(yaml_notes[-1])
            yaml_notes.append(note)

        note['position'] = n['position']
        note['duration'] = n['duration']
        note['tone'] = n['tone']
        note['lyric'] = n['lyric']
        # pitch 保持模板原样（空的或默认）
        if 'pitch' not in note:
            note['pitch'] = {'data': [{'x': 0, 'y': 0, 'shape': 'io'},
                                       {'x': 0, 'y': 0, 'shape': 'io'}],
                              'snap_first': (i == 0)}
        if 'vibrato' not in note:
            note['vibrato'] = {'length': 0, 'period': 175, 'depth': 25,
                               'in': 10, 'out': 10, 'shift': 0, 'drift': 0, 'vol_link': 0}
        if 'phoneme_expressions' not in note:
            note['phoneme_expressions'] = []
        if 'phoneme_overrides' not in note:
            note['phoneme_overrides'] = []

    # 截断多出来的 note（如果有）
    if len(yaml_notes) > len(notes):
        del yaml_notes[len(notes):]

    print(f"\n  替换后 voice_parts[0].notes 数: {len(vp['notes'])}")
    print(f"  lyric 样本 (前5): {[n['lyric'] for n in notes[:5]]}")
    print(f"  lyric 样本 (后3): {[n['lyric'] for n in notes[-3:]]}")

    # 5. 写文件
    with open(OUT, "w", encoding="utf-8") as f:
        yaml.dump(proj, f)

    size = os.path.getsize(OUT)
    print(f"\n[OK] {OUT}  ({size/1024:.1f} KB)")

    # 6. 验证：用纯文本 grep lyric
    text = open(OUT, encoding="utf-8").read()
    lyric_lines = re.findall(r'^\s+lyric:\s*(.+)$', text, re.MULTILINE)
    print(f"  lyric 行数: {len(lyric_lines)}")
    print(f"  lyric 文本(前5): {lyric_lines[:5]}")
    print(f"  lyric 文本(后3): {lyric_lines[-3:]}")

    # 7. 根级字段
    top_keys = [l.strip() for l in text.split("\n")
                if l and not l.startswith(" ") and ":" in l and not l.startswith("#")]
    print(f"\n  根级字段: {top_keys}")


if __name__ == "__main__":
    main()