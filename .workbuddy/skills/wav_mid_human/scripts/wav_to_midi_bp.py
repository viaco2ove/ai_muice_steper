#!/usr/bin/env python3
"""
wav_to_midi_bp.py - 人声 WAV 转 MIDI（basic_pitch 神经网络后端）

用 Spotify basic_pitch 神经网络模型转 MIDI，比 pyin 后端更贴合人声轮廓。
神经网络直接学习"什么是音符"，而非逐帧猜频率，因此能捕捉旋律细节。

依赖：basic_pitch + onnxruntime（项目 .venv 已装）
原理见 references/wav_to_mid_principles.md 的"方案选型"部分
"""

import argparse
import os
import sys
import csv
import warnings

warnings.filterwarnings("ignore")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
import logging; logging.disable(logging.CRITICAL)

try:
    from basic_pitch.inference import predict
except ImportError:
    print("[错误] 缺少 basic_pitch: pip install basic-pitch", file=sys.stderr)
    sys.exit(1)

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def midi_to_note(m: int) -> str:
    return f"{NOTE_NAMES[m % 12]}{(m // 12) - 1}"


def wav_to_midi_bp(
    input_wav: str,
    output_dir: str,
    onset_threshold: float = 0.6,  # 经 Melodyne 基准调参，0.6 比 0.5 更接近人声轮廓
    frame_threshold: float = 0.3,
    min_note_length: float = 127.7,  # 毫秒
    minimum_frequency: float = 180.0,  # Hz，过滤 C3 以下低频杂音（经 Melodyne 基准验证）
    maximum_frequency: float = None,
):
    """
    basic_pitch 转换。

    onset_threshold: 音符起始检测阈值（0-1），越高越严格（检出少但碎音少）
    frame_threshold: 音符持续帧阈值（0-1）
    min_note_length: 最小音符长度（毫秒），过滤碎音
    minimum_frequency: 最低频率 Hz，过滤低频杂音（如人声设 180 可滤掉 C3 以下误判）
    maximum_frequency: 最高频率 Hz，过滤高频泛音误判
    """
    os.makedirs(output_dir, exist_ok=True)
    print(f"[输入] {input_wav}")
    print("  basic_pitch 神经网络推理中（可能需 20-60s）...")

    model_output, midi_data, _ = predict(
        input_wav,
        onset_threshold=onset_threshold,
        frame_threshold=frame_threshold,
        minimum_note_length=min_note_length,
        minimum_frequency=minimum_frequency,
        maximum_frequency=maximum_frequency,
    )

    # 导出 MIDI
    mid_path = os.path.join(output_dir, "melody_basicpitch.mid")
    midi_data.write(mid_path)

    # 导出 CSV
    notes = []
    for inst in midi_data.instruments:
        for n in inst.notes:
            notes.append({
                "start": round(n.start, 3),
                "end": round(n.end, 3),
                "duration": round(n.end - n.start, 3),
                "note": midi_to_note(n.pitch),
                "midi": n.pitch,
                "velocity": n.velocity,
            })
    notes.sort(key=lambda x: x["start"])
    csv_path = os.path.join(output_dir, "melody_basicpitch.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["start", "end", "duration", "note", "midi", "velocity"])
        w.writeheader()
        w.writerows(notes)

    # 统计
    if notes:
        durs = [n["duration"] for n in notes]
        midis = [n["midi"] for n in notes]
        short_rate = sum(1 for d in durs if d < 0.05) / len(notes) * 100
        print(f"\n[输出] {mid_path}")
        print(f"   音符数: {len(notes)} | 碎音率(<50ms): {short_rate:.1f}%")
        print(f"   音域: {midi_to_note(min(midis))} ~ {midi_to_note(max(midis))}")
        print(f"   时长范围: {min(durs):.3f}s ~ {max(durs):.3f}s | 平均: {sum(durs)/len(durs):.3f}s")
        print(f"   带 velocity 起伏（人声力度映射）")
    else:
        print(f"\n[警告] 未提取到音符，请降低 onset_threshold")
    return notes


def main():
    ap = argparse.ArgumentParser(description="人声 WAV 转 MIDI（basic_pitch 神经网络后端）")
    ap.add_argument("input", help="输入 WAV 文件")
    ap.add_argument("-o", "--output", default=".", help="输出目录")
    ap.add_argument("--onset", type=float, default=0.6, help="音符起始阈值 0-1 (默认0.6，经Melodyne基准调参)")
    ap.add_argument("--frame", type=float, default=0.3, help="持续帧阈值 0-1 (默认0.3)")
    ap.add_argument("--min-len", type=float, default=127.7, help="最小音符长度ms (默认127.7)")
    ap.add_argument("--fmin", type=float, default=180.0, help="最低频率Hz，过滤低频杂音 (默认180，经Melodyne基准验证)")
    ap.add_argument("--fmax", type=float, default=None, help="最高频率Hz，过滤高频泛音误判")
    args = ap.parse_args()

    wav_to_midi_bp(
        args.input, args.output,
        onset_threshold=args.onset,
        frame_threshold=args.frame,
        min_note_length=args.min_len,
        minimum_frequency=args.fmin,
        maximum_frequency=args.fmax,
    )


if __name__ == "__main__":
    main()