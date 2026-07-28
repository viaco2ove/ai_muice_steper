#!/usr/bin/env python3
"""
recognize_melody.py - 旋律识别脚本
使用 librosa.pyin 提取基频 + basic-pitch 生成 MIDI
输出 pitch.csv 和 melody.mid
"""

import argparse
import os
import sys
import csv

try:
    import numpy as np
    import librosa
except ImportError:
    print("❌ 缺少 numpy 或 librosa，请运行: pip install numpy librosa -i https://mirrors.aliyun.com/pypi/simple/")
    sys.exit(1)


# MIDI 音符号表
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def midi_to_note(midi_num: int) -> str:
    """MIDI 编号转音名"""
    if midi_num is None or midi_num < 0:
        return "N/A"
    octave = (midi_num // 12) - 1
    note = NOTE_NAMES[midi_num % 12]
    return f"{note}{octave}"


def freq_to_midi(freq: float) -> int:
    """频率转 MIDI 编号"""
    if freq <= 0 or not isinstance(freq, (int, float)):
        return -1
    return int(round(69 + 12 * np.log2(freq / 440.0)))


def recognize_melody_librosa(
    y: np.ndarray,
    sr: int,
    fmin: float = 80.0,
    fmax: float = 1000.0,
) -> list[dict]:
    """
    使用 librosa.pyin 提取旋律基频

    Returns:
        List of dict: {time, freq, midi, note, voiced}
    """
    import numpy as np

    print("使用 librosa.pyin 提取旋律...")
    # f0: 基频, voiced_flag: 是否为有声帧, voiced_probs: 有声概率
    f0, voiced_flag, voiced_probs = librosa.pyin(
        y, fmin=fmin, fmax=fmax, sr=sr,
        frame_length=2048, hop_length=512
    )

    times = librosa.times_like(f0, sr=sr, hop_length=512)

    results = []
    for t, freq, voiced, prob in zip(times, f0, voiced_flag, voiced_probs):
        if voiced and freq > 0:
            midi = freq_to_midi(freq)
            note = midi_to_note(midi)
        else:
            midi = -1
            note = "N/A"
        results.append({
            "time": round(float(t), 3),
            "freq": round(float(freq), 2) if voiced and freq > 0 else 0.0,
            "midi": midi,
            "note": note,
            "prob": round(float(prob), 3),
        })
    return results


def export_csv(results: list[dict], output_path: str):
    """导出为 CSV"""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["time", "freq", "note", "midi", "prob"])
        writer.writeheader()
        writer.writerows(results)
    print(f"  ✅ pitch.csv → {output_path}")


def export_midi(results: list[dict], output_path: str, velocity: int = 80):
    """
    将旋律结果导出为 MIDI 文件
    相邻同音合并为一个 note，减少 MIDI 噪音
    """
    import numpy as np
    try:
        import mido
    except ImportError:
        print("⚠️  缺少 mido，跳过 MIDI 导出")
        return

    print(f"生成 MIDI: {output_path}")
    mid = mido.MidiFile()
    mid.ticks_per_beat = 480

    track = mido.MidiTrack()
    mid.tracks.append(track)

    # 设置音色（钢琴）
    track.append(mido.Message("program_change", program=0, time=0))

    last_midi = None
    last_start_tick = None
    ticks_per_sec = mid.ticks_per_beat * 2  # 假设 120 BPM

    def sec_to_tick(t):
        return int(t * ticks_per_sec)

    for i, row in enumerate(results):
        midi = row["midi"]
        t = row["time"]

        if midi < 0:
            # 无声帧：关闭之前的音符
            if last_midi is not None:
                end_tick = sec_to_tick(t)
                track.append(mido.Message("note_off", note=last_midi,
                                          velocity=0, time=end_tick - last_start_tick))
                last_midi = None
            continue

        if last_midi is None:
            # 开始新音符
            start_tick = sec_to_tick(t)
            track.append(mido.Message("note_on", note=midi, velocity=velocity, time=0))
            last_midi = midi
            last_start_tick = start_tick
        elif midi != last_midi:
            # 换音：关闭旧音符，开启新音符
            end_tick = sec_to_tick(t)
            track.append(mido.Message("note_off", note=last_midi,
                                      velocity=0, time=end_tick - last_start_tick))
            track.append(mido.Message("note_on", note=midi, velocity=velocity, time=0))
            last_midi = midi
            last_start_tick = end_tick

    # 关闭最后的音符
    if last_midi is not None and results:
        last_t = results[-1]["time"]
        end_tick = sec_to_tick(last_t + 0.3)
        track.append(mido.Message("note_off", note=last_midi,
                                  velocity=0, time=end_tick - last_start_tick))

    track.append(mido.MetaMessage("end_of_track", time=0))
    mid.save(output_path)
    print(f"  ✅ melody.mid → {output_path}")


def recognize_basic_pitch(input_path: str, output_dir: str) -> bool:
    """
    尝试使用 basic-pitch 识别旋律并生成 MIDI
    basic-pitch 是 Spotify 开源的音频转 MIDI 工具
    """
    try:
        from basic_pitch.inference import predict
        from basic_pitch import note_manipulation
        import tensorflow as tf
        tf.get_logger().setLevel("ERROR")  # 禁用 TF 日志
    except ImportError:
        return False

    print("使用 basic-pitch 补充生成 MIDI...")
    try:
        # 预测
        _, midi_data, _ = predict(input_path)
        out_path = os.path.join(output_dir, "basic_pitch.mid")
        with open(out_path, "wb") as f:
            f.write(midi_data.read())
        print(f"  ✅ basic_pitch.mid → {out_path}")
        return True
    except Exception as e:
        print(f"  ⚠️  basic-pitch 失败: {e}")
        return False


def main():
    import numpy as np

    parser = argparse.ArgumentParser(
        description="识别音频旋律并生成 MIDI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python recognize_melody.py song.wav -o melody/
  python recognize_melody.py vocals.wav -o output/ --fmin 100 --fmax 800

输出:
  pitch.csv        - 时间, 频率, 音名, MIDI编号, 有声概率
  melody.mid       - 旋律 MIDI 文件（librosa.pyin）
  basic_pitch.mid  - 旋律 MIDI 文件（basic-pitch，可选）
        """
    )
    parser.add_argument("input", help="输入音频文件路径")
    parser.add_argument("-o", "--output", default="melody", help="输出目录 (default: melody)")
    parser.add_argument("--fmin", type=float, default=80.0,
                        help="最低检测频率 Hz (default: 80)")
    parser.add_argument("--fmax", type=float, default=1000.0,
                        help="最高检测频率 Hz (default: 1000)")
    parser.add_argument("--velocity", type=int, default=80,
                        help="MIDI 音符力度 1-127 (default: 80)")
    args = parser.parse_args()

    input_path = os.path.expanduser(args.input)
    if not os.path.exists(input_path):
        print(f"❌ 文件不存在: {input_path}")
        sys.exit(1)

    os.makedirs(args.output, exist_ok=True)

    print(f"加载音频: {input_path}")
    y, sr = librosa.load(input_path, sr=None, mono=True)
    print(f"采样率: {sr}Hz, 时长: {len(y)/sr:.1f}s")

    # librosa.pyin 旋律识别
    results = recognize_melody_librosa(y, sr, fmin=args.fmin, fmax=args.fmax)

    csv_path = os.path.join(args.output, "pitch.csv")
    export_csv(results, csv_path)

    midi_path = os.path.join(args.output, "melody.mid")
    export_midi(results, midi_path, velocity=args.velocity)

    # basic-pitch（可选）
    recognize_basic_pitch(input_path, args.output)

    # 统计
    voiced = [r for r in results if r["midi"] >= 0]
    notes = set(r["note"] for r in voiced)
    print(f"\n✅ 完成！检测到 {len(voiced)} 个旋律帧，涉及音高: {sorted(notes)}")
    print(f"输出目录: {args.output}")


if __name__ == "__main__":
    main()