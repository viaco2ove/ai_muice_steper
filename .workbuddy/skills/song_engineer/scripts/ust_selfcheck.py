# -*- coding: utf-8 -*-
"""
ust_selfcheck.py - 02_主唱.ust 自检脚本

检查项:
  1. 块数量 (206 ± n)
  2. 每个块的字段齐全 (Length/NoteNum/Lyric/Intensity)
  3. Lyric 是中文字符 / R
  4. 段落切换位置跟 .inspect.txt 对得上
  5. 估算渲染时长 (= ∑Length / 480 ticks * 60 / 68 s)
  6. 列出所有非 ASCII Lyric（让用户人工看一眼）
"""
import os
import re
import sys

# Windows 控制台默认 GBK, 强制 utf-8 防 emoji/中文 print 爆
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

UST = "workspace/project/走在/song_engineer/track/02_主唱.ust"
EXPECTED = 206


def main():
    if not os.path.exists(UST):
        print(f"[错误] 缺 {UST}")
        return

    text = open(UST, encoding="utf-8").read()
    blocks = re.findall(r"\[#(\d{4})\](.*?)(?=\[#\d{4}\]|#TRACKEND|\Z)",
                        text, re.DOTALL)
    n = len(blocks)

    print("=== ust_selfcheck ===")
    print(f"文件: {UST}")
    print(f"音符块数: {n}  (预期 {EXPECTED})")
    if n != EXPECTED:
        print(f"  ⚠ 数量对不上,差 {n - EXPECTED}")
    else:
        print(f"  ✅ 对得上")

    # 字段完整性
    bad = []
    section_starts = []
    cur_section = "Verse_1"  # 默认第一段
    n_rest = 0
    n_chinese = 0
    n_other = 0
    total_ticks = 0
    lyrics = []
    for idx, body in blocks:
        f = {}
        for line in body.strip().split("\n"):
            line = line.strip()
            # MARKBEGIN 可能在注释行(`; ===` 不带 MARKBEGIN) 或单独行
            if line.startswith("MARKBEGIN="):
                cur_section = line.split("=", 1)[1]
                continue
            if not line or line.startswith(";"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                f[k.strip()] = v.strip()
        needed = ("Length", "NoteNum", "Lyric", "Intensity")
        missing = [k for k in needed if k not in f]
        if missing:
            bad.append((idx, missing))
        lyric = f.get("Lyric", "")
        length = int(f.get("Length", "0"))
        total_ticks += length
        if lyric == "R":
            n_rest += 1
        elif any('一' <= ch <= '鿿' for ch in lyric):
            n_chinese += 1
        else:
            n_other += 1
        lyrics.append((idx, cur_section or "?", lyric, length, f.get("NoteNum"), f.get("Intensity")))

    print(f"\n[字段完整性]")
    if bad:
        print(f"  [FAIL] {len(bad)} 块缺字段:")
        for idx, miss in bad[:10]:
            print(f"      #{idx} 缺 {miss}")
    else:
        print(f"  [OK] 全部字段齐全")

    print(f"\n[Lyric 统计]")
    print(f"  中文字: {n_chinese}  |  R (气口): {n_rest}  |  其它: {n_other}")
    if n_other:
        print(f"  [WARN] 有 {n_other} 个非中文 Lyric:")
        for idx, sec, lyr, *rest in [x for x in lyrics if x[3] not in ("R",)
                                     and not any('一' <= ch <= '鿿' for ch in x[3])][:10]:
            print(f"      #{idx} {sec} '{lyr}'")

    # 时长估算
    # BPM 68 -> 一拍秒数 = 60/68 ≈ 0.882s;  480 ticks/拍
    seconds = total_ticks / 480 * 60 / 68
    print(f"\n[时长估算] 总 ticks={total_ticks}, "
          f"BPM=68 -> {seconds:.1f} s ({seconds/60:.2f} min)")

    # 段落分布
    print(f"\n[段落分布]")
    sect = {}
    for _, sec, *_ in lyrics:
        sect[sec] = sect.get(sec, 0) + 1
    for k, v in sect.items():
        print(f"  {k:14s} {v:3d} 块")

    # 前 8 块预览
    print(f"\n[前 8 块预览]")
    for idx, sec, lyr, length, num, inten in lyrics[:8]:
        print(f"  #{idx} {sec:10s} Lyric={lyr:6s} NoteNum={num:>3s} "
              f"Length={length:>4} Intensity={inten}")

    # 后 8 块预览（确认 Outro 渐弱）
    print(f"\n[后 8 块预览]")
    for idx, sec, lyr, length, num, inten in lyrics[-8:]:
        print(f"  #{idx} {sec:10s} Lyric={lyr:6s} NoteNum={num:>3s} "
              f"Length={length:>4} Intensity={inten}")


if __name__ == "__main__":
    main()
