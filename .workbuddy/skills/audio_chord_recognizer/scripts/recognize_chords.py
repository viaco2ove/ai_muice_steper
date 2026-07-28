#!/usr/bin/env python3
"""
recognize_chords.py - 基于 librosa chroma 特征 + 模板匹配识别和弦进行
支持: maj/min/maj7/min7/7/sus4/sus2/dim/aug
"""

import argparse
import os
import sys
import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

try:
    import librosa
except ImportError:
    print("[ERROR] 缺少 librosa，请运行: pip install librosa")
    sys.exit(1)


# 和弦根音（C, C#/Db, D, D#/Eb, E, F, F#/Gb, G, G#/Ab, A, A#/Bb, B）
PITCHES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# 简写映射（用于输出）
PITCH_ALIASES = {
    "C": "C", "C#": "C#", "Db": "Db",
    "D": "D", "D#": "D#", "Eb": "Eb",
    "E": "E", "Fb": "E", "En": "E",
    "F": "F", "F#": "F#", "Gb": "Gb",
    "G": "G", "G#": "G#", "Ab": "Ab",
    "A": "A", "A#": "A#", "Bb": "Bb",
    "B": "B", "Cb": "B", "Bn": "B",
}


def build_chord_templates() -> dict[str, np.ndarray]:
    """
    构建 9 种和弦类型的模板（12 维 chroma 向量）
    基于三度叠置和弦的音程结构
    """
    # 各音级相对于根音的半音数
    intervals = {
        "maj":     [0, 4, 7],        # 大三和弦
        "min":     [0, 3, 7],        # 小三和弦
        "maj7":    [0, 4, 7, 11],    # 大七和弦
        "min7":    [0, 3, 7, 10],    # 小七和弦
        "7":       [0, 4, 7, 10],    # 属七和弦
        "sus4":    [0, 5, 7],        # 挂四和弦
        "sus2":    [0, 2, 7],        # 挂二和弦
        "dim":     [0, 3, 6],        # 减三和弦
        "aug":     [0, 4, 8],        # 增三和弦
    }

    templates = {}
    for chord_type, semitones in intervals.items():
        vec = np.zeros(12)
        for s in semitones:
            vec[s % 12] += 1
        # 归一化
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        templates[chord_type] = vec

    return templates


def recognize_chords(
    y: np.ndarray,
    sr: int,
    hop_length: int = 512,
    window_sec: float = 0.5,
) -> list[tuple[float, str, float]]:
    """
    识别音频的和弦进行

    Args:
        y: 音频波形
        sr: 采样率
        hop_length: hop 长度（帧移）
        window_sec: 分析窗口秒数

    Returns:
        List of (start_sec, chord_name, confidence)
    """
    templates = build_chord_templates()

    # 计算 hop 秒数
    hop_sec = hop_length / sr

    # 计算 chroma
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop_length)

    # 窗口大小（帧数）
    win_frames = max(1, int(window_sec / hop_sec))

    results = []
    n_frames = chroma.shape[1]

    for i in range(0, n_frames, win_frames):
        start_frame = i
        end_frame = min(i + win_frames, n_frames)

        # 该窗口的平均 chroma
        window_chroma = chroma[:, start_frame:end_frame].mean(axis=1)

        # 与所有和弦模板匹配
        best_chord = None
        best_score = -1

        for root_idx in range(12):
            root_name = PITCHES[root_idx]
            for chord_type, template in templates.items():
                # 将模板旋转到对应根音
                rotated = np.roll(template, root_idx)
                # 余弦相似度
                score = np.dot(window_chroma, rotated)

                if score > best_score:
                    best_score = score
                    best_chord = f"{root_name}:{chord_type}"

        start_sec = i * hop_sec
        results.append((start_sec, best_chord, round(float(best_score), 3)))

    return results


def main():
    parser = argparse.ArgumentParser(
        description="识别音频和弦进行",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python recognize_chords.py song.wav -o chords.txt
  python recognize_chords.py vocals.wav -o chords.txt --hop 0.25
  python recognize_chords.py input.wav -o chords.txt --hop 0.5 --window 1.0

输出格式（chords.txt）:
  0.0   C:maj  0.85
  0.5   G:min  0.78
  1.0   Am     0.82
        """
    )
    parser.add_argument("input", help="输入音频文件路径")
    parser.add_argument("-o", "--output", required=True, help="输出文件路径")
    parser.add_argument("--hop", type=float, default=0.5,
                        help="分析窗口滑动步长（秒）(default: 0.5)")
    parser.add_argument("--window", type=float, default=0.5,
                        help="分析窗口长度（秒）(default: 0.5)")
    args = parser.parse_args()

    input_path = os.path.expanduser(args.input)
    if not os.path.exists(input_path):
        print(f"[ERROR] 文件不存在: {input_path}")
        sys.exit(1)

    print(f"加载音频: {input_path}")
    y, sr = librosa.load(input_path, sr=None, mono=True)
    print(f"采样率: {sr}Hz, 时长: {len(y)/sr:.1f}s")

    hop_length = int(args.hop * sr) if args.hop else 512

    print(f"分析中（窗口 {args.window}s, 步长 {args.hop}s）...")
    results = recognize_chords(y, sr, hop_length=hop_length, window_sec=args.window)

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write("# 和弦识别结果\n")
        f.write("# 格式: 时间(秒)  和弦  置信度\n")
        f.write("# 根音: C C# D D# E F F# G G# A A# B\n")
        f.write("# 类型: maj/min/maj7/min7/7/sus4/sus2/dim/aug\n\n")
        for start_sec, chord, conf in results:
            f.write(f"{start_sec:.2f}  {chord:<10} {conf:.3f}\n")

    print(f"\n[OK] 完成，{len(results)} 个和弦，输出到: {args.output}")

    # 打印摘要
    unique_chords = set(c for _, c, _ in results)
    print(f"涉及和弦: {', '.join(sorted(unique_chords))}")


if __name__ == "__main__":
    main()
