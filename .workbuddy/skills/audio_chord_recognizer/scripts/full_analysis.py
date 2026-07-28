#!/usr/bin/env python3
"""
full_analysis.py - 音频一键全流程分析
依次执行：分离音轨 → 识别和弦 → 识别旋律 → 生成 report.md
"""

import argparse
import os
import sys
import subprocess
import datetime
from pathlib import Path

# 尝试导入可选依赖，缺失时给出友好提示
try:
    import numpy as np
    import librosa
except ImportError:
    print("❌ 缺少必要依赖，请运行安装脚本:")
    print("  python scripts/setup.py")
    sys.exit(1)


def run_separate(input_path: str, work_dir: str) -> str:
    """分离音轨"""
    import torch
    import soundfile as sf
    from demucs.pretrained import get_model
    from demucs.apply import apply_model

    print("\n" + "=" * 60)
    print("Step 1/4: 分离音轨 (demucs)")
    print("=" * 60)

    tracks_dir = os.path.join(work_dir, "tracks")
    os.makedirs(tracks_dir, exist_ok=True)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"设备: {device}")

    model = get_model("htdemucs")
    model.eval()
    if device == "cuda":
        model = model.to(device)

    import soundfile as sf

    # 用 soundfile 加载（MP3 先用 ffmpeg 转 WAV 绕过损坏问题）
    y, sr = sf.read(input_path, dtype='float32')
    if y.ndim == 1:
        y = y[np.newaxis, :]  # (channels, samples)
    else:
        y = y.T  # (samples, channels) -> (channels, samples)
    # 重采样到 44100
    if sr != 44100:
        import librosa
        y = librosa.resample(y, orig_sr=sr, target_sr=44100)
        sr = 44100
    # demucs 需要立体声，单声道复制为双声道
    if y.shape[0] == 1:
        y = np.concatenate([y, y], axis=0)
    mixture = torch.tensor(y, dtype=torch.float32).unsqueeze(0)
    if device == "cuda":
        mixture = mixture.to(device)

    with torch.no_grad():
        sources = apply_model(model, mixture, device=device, progress=True)

    track_names = list(model.sources)
    for i, name in enumerate(track_names):
        track_waveform = sources[0, i].cpu().numpy()
        out_path = os.path.join(tracks_dir, f"{name}.wav")
        sf.write(out_path, track_waveform.T, sr)  # (samples, channels)

    print(f"✅ 分离完成: {tracks_dir}")
    return tracks_dir


def run_chord_recognize(track_path: str, work_dir: str) -> str:
    """识别和弦"""
    print("\n" + "=" * 60)
    print("Step 2/4: 识别和弦 (librosa chroma)")
    print("=" * 60)

    import sys
    import soundfile as sf
    sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
    from recognize_chords import recognize_chords, build_chord_templates

    y, sr = sf.read(track_path, dtype='float32')
    if y.ndim > 1:
        y = y.mean(axis=1)
    results = recognize_chords(y, sr, hop_length=512, window_sec=0.5)

    chords_path = os.path.join(work_dir, "chords.txt")
    with open(chords_path, "w", encoding="utf-8") as f:
        f.write("# 和弦识别结果\n")
        for start_sec, chord, conf in results:
            f.write(f"{start_sec:.2f}  {chord:<10} {conf:.3f}\n")

    unique = set(c for _, c, _ in results)
    print(f"✅ 和弦识别完成: {len(results)} 个和弦，涉及 {len(unique)} 种和弦")
    print(f"   和弦进行: {' → '.join(c for _, c, _ in results[:20])}")
    return chords_path, results


def run_melody_recognize(track_path: str, work_dir: str) -> str:
    """识别旋律"""
    print("\n" + "=" * 60)
    print("Step 3/4: 识别旋律 (librosa.pyin)")
    print("=" * 60)

    import soundfile as sf
    sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
    from recognize_melody import recognize_melody_librosa, export_csv, export_midi

    melody_dir = os.path.join(work_dir, "melody")
    os.makedirs(melody_dir, exist_ok=True)

    y, sr = sf.read(track_path, dtype='float32')
    if y.ndim > 1:
        y = y.mean(axis=1)  # 转单声道
    results = recognize_melody_librosa(y, sr)

    csv_path = os.path.join(melody_dir, "pitch.csv")
    export_csv(results, csv_path)

    midi_path = os.path.join(melody_dir, "melody.mid")
    export_midi(results, midi_path)

    voiced = [r for r in results if r["midi"] >= 0]
    notes = set(r["note"] for r in voiced)
    print(f"✅ 旋律识别完成: {len(voiced)} 个旋律帧")
    print(f"   音域: {min(notes)} ~ {max(notes)}")
    return melody_dir, results


def generate_report(
    work_dir: str,
    input_name: str,
    tracks_dir: str,
    chords_path: str,
    chord_results: list,
    melody_dir: str,
    melody_results: list,
) -> str:
    """生成 report.md"""
    print("\n" + "=" * 60)
    print("Step 4/4: 生成分析报告")
    print("=" * 60)

    report_path = os.path.join(work_dir, "report.md")

    # 基本信息
    total_dur = max(r["time"] for r in melody_results) if melody_results else 0

    # 和弦统计
    unique_chords = {}
    for _, chord, conf in chord_results:
        if chord not in unique_chords:
            unique_chords[chord] = {"count": 0, "avg_conf": []}
        unique_chords[chord]["count"] += 1
        unique_chords[chord]["avg_conf"].append(conf)

    # 旋律统计
    voiced = [r for r in melody_results if r["midi"] >= 0]
    midi_vals = [r["midi"] for r in voiced]
    if midi_vals:
        avg_midi = sum(midi_vals) / len(midi_vals)
        min_midi, max_midi = min(midi_vals), max(midi_vals)

        def midi_to_note(n):
            NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
            return f"{NOTE_NAMES[n % 12]}{n // 12 - 1}"
    else:
        avg_midi = min_midi = max_midi = 0

    # 推断调性（基于最常见的大/小和弦）
    chord_roots = {}
    for _, chord, _ in chord_results:
        root = chord.split(":")[0]
        chord_roots[root] = chord_roots.get(root, 0) + 1

    # 生成 markdown
    lines = [
        f"# 音频分析报告",
        "",
        f"**源文件**: {input_name}",
        f"**分析时间**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "---",
        "",
        "## 1. 音轨分离结果",
        "",
        "使用 demucs HTDemucs 模型分离为 4 个音轨：",
        "",
        "| 音轨 | 文件 | 说明 |",
        "|------|------|------|",
    ]

    for name in ["vocals", "drums", "bass", "other"]:
        fname = f"{name}.wav"
        fpath = os.path.join(tracks_dir, fname)
        size_mb = os.path.getsize(fpath) / 1024 / 1024 if os.path.exists(fpath) else 0
        desc = {"vocals": "人声", "drums": "鼓组", "bass": "贝斯", "other": "其他乐器"}.get(name, "")
        lines.append(f"| {name} | `{fname}` | {desc} |")

    lines += [
        "",
        "## 2. 和弦进行",
        "",
        f"**识别和弦数**: {len(chord_results)} 个",
        f"**涉及和弦类型**: {len(unique_chords)} 种",
        "",
        "### 和弦时间线",
        "",
        "```",
    ]

    for start, chord, conf in chord_results:
        bar = "█" * int(conf * 10)
        lines.append(f"{start:6.2f}s  {chord:<10}  {conf:.2f}  {bar}")

    lines += [
        "```",
        "",
        "### 和弦频率统计",
        "",
        "| 和弦 | 出现次数 | 平均置信度 |",
        "|------|---------|-----------|",
    ]

    sorted_chords = sorted(unique_chords.items(), key=lambda x: x[1]["count"], reverse=True)
    for chord, info in sorted_chords:
        avg_c = sum(info["avg_conf"]) / len(info["avg_conf"])
        lines.append(f"| {chord} | {info['count']} | {avg_c:.2f} |")

    lines += [
        "",
        "## 3. 旋律分析",
        "",
        f"**旋律帧数**: {len(voiced)} / {len(melody_results)} 帧",
        f"**平均音高**: {midi_to_note(int(avg_midi))} (MIDI {avg_midi:.0f})",
        f"**音域**: {midi_to_note(min_midi)} ~ {midi_to_note(max_midi)}",
        "",
        "### 前 20 个旋律音符",
        "",
        "| 时间(s) | 音名 | MIDI | 频率(Hz) | 置信度 |",
        "|---------|------|------|---------|--------|",
    ]

    for r in voiced[:20]:
        lines.append(
            f"| {r['time']:.3f} | {r['note']} | {r['midi']} | "
            f"{r['freq']:.1f} | {r['prob']:.2f} |"
        )

    lines += [
        "",
        f"完整旋律数据: `melody/pitch.csv`",
        f"MIDI 文件: `melody/melody.mid`",
        "",
        "## 4. 分析摘要",
        "",
        "```",
    ]

    # 自动推断风格/情绪（简单启发式）
    major_count = sum(1 for _, c, _ in chord_results if ":maj" in c or ":min" not in c)
    minor_ratio = (len(chord_results) - major_count) / max(len(chord_results), 1)
    if minor_ratio > 0.6:
        mood = "偏忧伤/深沉"
    elif minor_ratio > 0.3:
        mood = "中性偏抒情"
    else:
        mood = "明亮/积极"

    lines += [
        f"总时长:     {total_dur:.1f}s",
        f"调性推断:   {'小调' if minor_ratio > 0.5 else '大调'}倾向 (min ratio={minor_ratio:.1%})",
        f"情绪风格:   {mood}",
        f"和弦密度:   {len(chord_results) / max(total_dur, 1):.1f} 和弦/秒",
        f"旋律音域:   {(max_midi - min_midi)} 半音",
        "```",
        "",
        "---",
        "*由 audio_chord_recognizer 自动生成*",
    ]

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"✅ 报告已生成: {report_path}")
    return report_path


def main():
    parser = argparse.ArgumentParser(
        description="音频一键全流程分析：分离音轨 → 和弦识别 → 旋律识别 → 生成报告",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/full_analysis.py song.mp3 -o output/
  python scripts/full_analysis.py audio.wav -o results/
        """
    )
    parser.add_argument("input", help="输入音频文件 (mp3/wav/flac/ogg...)")
    parser.add_argument("-o", "--output", default="analysis_output",
                        help="输出目录 (default: analysis_output)")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser()
    if not input_path.exists():
        print(f"❌ 文件不存在: {input_path}")
        sys.exit(1)

    work_dir = Path(args.output).expanduser()
    os.makedirs(work_dir, exist_ok=True)

    print("=" * 60)
    print("Audio Chord Recognizer - 全流程分析")
    print("=" * 60)
    print(f"输入文件: {input_path.name}")
    print(f"输出目录: {work_dir}")

    try:
        # Step 1: 分离音轨
        tracks_dir = run_separate(str(input_path), str(work_dir))

        # Step 2: 和弦识别（使用 other 轨，避开人声干扰）
        other_track = os.path.join(tracks_dir, "other.wav")
        if not os.path.exists(other_track):
            other_track = os.path.join(tracks_dir, "vocals.wav")
        chords_path, chord_results = run_chord_recognize(other_track, str(work_dir))

        # Step 3: 旋律识别（使用 vocals 轨）
        vocals_track = os.path.join(tracks_dir, "vocals.wav")
        melody_dir, melody_results = run_melody_recognize(vocals_track, str(work_dir))

        # Step 4: 生成报告
        report_path = generate_report(
            str(work_dir),
            input_path.name,
            tracks_dir,
            chords_path,
            chord_results,
            melody_dir,
            melody_results,
        )

        print("\n" + "=" * 60)
        print("✅ 全部分析完成！")
        print("=" * 60)
        print(f"\n输出目录: {work_dir}")
        print(f"  ├── tracks/          # 分离的 4 轨音频")
        print(f"  ├── chords.txt       # 和弦时间线")
        print(f"  ├── melody/          # 旋律 CSV + MIDI")
        print(f"  └── report.md        # 完整分析报告")
        print(f"\n打开报告: {report_path}")

    except Exception as e:
        print(f"\n❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()