#!/usr/bin/env python3
"""
wav_to_midi.py - 人声 WAV 转 MIDI（可听出旋律线版）

针对 recognize_melody.py 的碎音问题做完整清洗管线：
加载 -> 预处理 -> pyin 提取 -> 有声帧过滤 -> 中值滤波 -> 跳变修正
-> 音符合并 -> 碎音过滤 -> 导出干净 MIDI

原理见 references/wav_to_mid_principles.md
依赖：librosa / soundfile / mido / numpy / scipy（项目 .venv 已装）
"""

import argparse
import os
import sys
import csv
import warnings

warnings.filterwarnings("ignore")

import numpy as np

try:
    import soundfile as sf
except ImportError:
    print("[错误] 缺少 soundfile: pip install soundfile", file=sys.stderr)
    sys.exit(1)

try:
    import librosa
except ImportError:
    print("[错误] 缺少 librosa", file=sys.stderr)
    sys.exit(1)

try:
    import mido
except ImportError:
    print("[错误] 缺少 mido", file=sys.stderr)
    sys.exit(1)


NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def midi_to_note(m: int) -> str:
    if m is None or m < 0:
        return "N/A"
    return f"{NOTE_NAMES[m % 12]}{(m // 12) - 1}"


def freq_to_midi(f: float) -> int:
    if f is None or f <= 0:
        return -1
    return int(round(69 + 12 * np.log2(f / 440.0)))


# ---------- Step 1: 加载 ----------
def load_audio(path: str, sr: int = 22050) -> tuple[np.ndarray, int]:
    """用 soundfile 加载（绕过 audioread 版本问题），转 mono"""
    y, sr_orig = sf.read(path)
    if y.ndim > 1:
        y = y[:, 0]
    y = y.astype(np.float32)
    if sr != sr_orig:
        y = librosa.resample(y, orig_sr=sr_orig, target_sr=sr)
    else:
        sr = sr_orig
    return y, sr


# ---------- Step 2: 预处理 ----------
def preprocess(y: np.ndarray, sr: int, noise_gate_db: float = -40.0) -> np.ndarray:
    """归一化 + 简易 noise gate（压低极安静段的底噪/呼吸）"""
    peak = np.max(np.abs(y)) + 1e-9
    y = y / peak  # 归一化到 [-1,1]
    gate = 10 ** (noise_gate_db / 20.0)
    mask = np.abs(y) < gate
    y = y * (~mask)  # 低于 gate 的样本置零
    return y.astype(np.float32)


# ---------- Step 3: pyin 音高提取 ----------
def extract_pitch(
    y: np.ndarray, sr: int, fmin: float, fmax: float,
    frame_length: int = 2048, hop_length: int = 512,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """librosa.pyin 提取 f0 / voiced_flag / voiced_probs"""
    f0, voiced_flag, voiced_probs = librosa.pyin(
        y, fmin=fmin, fmax=fmax, sr=sr,
        frame_length=frame_length, hop_length=hop_length,
        fill_na=np.nan,
    )
    return f0, voiced_flag, voiced_probs


# ---------- Step 4: 有声帧过滤 ----------
def filter_voiced(f0: np.ndarray, voiced_flag: np.ndarray) -> np.ndarray:
    """只保留 voiced 帧，无声帧置 nan"""
    f0_clean = f0.copy()
    f0_clean[~voiced_flag] = np.nan
    return f0_clean


# ---------- Step 5: 中值滤波 ----------
def median_filter_f0(f0: np.ndarray, window: int = 5) -> np.ndarray:
    """对 f0 序列做中值滤波，消除单帧跳变（nan 段不参与）"""
    from scipy.ndimage import median_filter
    # 用 nan 到 0 的临时数组做滤波，再恢复 nan
    mask = np.isnan(f0)
    f0_filled = np.where(mask, 0.0, f0)
    f0_filt = median_filter(f0_filled, size=window, mode="nearest")
    # 恢复 nan
    f0_filt[mask] = np.nan
    return f0_filt


# ---------- Step 6: 音程跳变修正 ----------
def fix_octave_jumps(f0: np.ndarray, max_jump_semitones: int = 7, persist_frames: int = 3) -> np.ndarray:
    """相邻帧音程 > max_jump 且持续 < persist_frames 帧的视为误判，用前一个有效值替代"""
    midi = np.array([freq_to_midi(f) if not np.isnan(f) else -1 for f in f0], dtype=float)
    out = midi.copy()
    n = len(out)
    i = 1
    while i < n:
        if out[i] < 0 or out[i - 1] < 0:
            i += 1
            continue
        jump = abs(out[i] - out[i - 1])
        if jump > max_jump_semitones:
            # 检查这个跳变持续多少帧
            j = i
            while j < n and out[j] >= 0 and abs(out[j] - out[i - 1]) > max_jump_semitones:
                j += 1
            persist = j - i
            if persist < persist_frames:
                # 短跳变，用前值填充
                out[i:j] = out[i - 1]
            i = j
        else:
            i += 1
    # 回到频率（用 midi 反推近似频率，仅用于后续合并）
    return out  # 返回 midi 序列（-1 = 无声）


# ---------- Step 7: 音符合并 ----------
def merge_notes(midi_seq: np.ndarray, hop_length: int, sr: int, merge_tolerance: int = 1) -> list[dict]:
    """连续相同/相近（±merge_tolerance 半音）的帧合并为一个音符"""
    hop_sec = hop_length / sr
    notes = []
    i = 0
    n = len(midi_seq)
    while i < n:
        if midi_seq[i] < 0:
            i += 1
            continue
        # 起始
        start_midi = midi_seq[i]
        start_time = i * hop_sec
        j = i + 1
        # 合并：相邻帧 midi 差 <= tolerance 视为同一音符，取众数为代表音高
        segment = [start_midi]
        while j < n and midi_seq[j] >= 0 and abs(midi_seq[j] - start_midi) <= merge_tolerance:
            segment.append(midi_seq[j])
            j += 1
        end_time = j * hop_sec
        # 代表音高 = 段内中位数（四舍五入）
        note_midi = int(round(np.median(segment)))
        notes.append({
            "start": round(start_time, 3),
            "end": round(end_time, 3),
            "duration": round(end_time - start_time, 3),
            "midi": note_midi,
            "note": midi_to_note(note_midi),
            "frames": len(segment),
        })
        i = j
    return notes


# ---------- Step 8: 碎音过滤 ----------
def filter_short_notes(notes: list[dict], min_dur: float = 0.08, fmin_midi: int = None, fmax_midi: int = None) -> list[dict]:
    """丢弃时长 < min_dur 的碎音；丢弃音域外的音符（过滤低频呼吸/底噪误判）"""
    kept = []
    for nt in notes:
        if nt["duration"] < min_dur:
            continue
        if fmin_midi is not None and nt["midi"] < fmin_midi:
            continue
        if fmax_midi is not None and nt["midi"] > fmax_midi:
            continue
        kept.append(nt)
    return kept


# ---------- 导出 ----------
def export_midi(notes: list[dict], output_path: str, sr: int, velocity_base: int = 70):
    """导出单轨钢琴 MIDI，音符带力度（按持续时间映射）"""
    mid = mido.MidiFile()
    mid.ticks_per_beat = 480
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("track_name", name="vocal melody", time=0))
    track.append(mido.Message("program_change", program=0, time=0))  # 钢琴

    ticks_per_sec = mid.ticks_per_beat * 2  # 假设 120 BPM
    last_end_tick = 0
    for nt in notes:
        start_tick = int(nt["start"] * ticks_per_sec)
        end_tick = int(nt["end"] * ticks_per_sec)
        dur = nt["duration"]
        # 力度：短音弱，长音稍强，限制在 50-95
        vel = int(np.clip(velocity_base + dur * 40, 50, 95))
        delta = max(0, start_tick - last_end_tick)
        track.append(mido.Message("note_on", note=nt["midi"], velocity=vel, time=delta))
        track.append(mido.Message("note_off", note=nt["midi"], velocity=0, time=end_tick - start_tick))
        last_end_tick = end_tick
    mid.save(output_path)
    return len(notes)


def export_csv(notes: list[dict], output_path: str):
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["start", "end", "duration", "note", "midi", "frames"])
        w.writeheader()
        w.writerows(notes)


# ---------- 主流程 ----------
def wav_to_midi(
    input_wav: str,
    output_dir: str,
    fmin: float = 80.0,
    fmax: float = 800.0,
    min_note_dur: float = 0.08,
    median_window: int = 5,
    max_jump: int = 7,
    merge_tolerance: int = 1,
    frame_length: int = 2048,
    hop_length: int = 512,
    sr: int = 22050,
):
    os.makedirs(output_dir, exist_ok=True)
    print(f"[输入]: {input_wav}")

    # Step 1
    y, sr = load_audio(input_wav, sr)
    print(f"  [1/8] 加载完成: {len(y)/sr:.1f}s, sr={sr}")

    # Step 2
    y = preprocess(y, sr)
    print(f"  [2/8] 预处理（归一化+noise gate）完成")

    # Step 3
    f0, voiced_flag, voiced_probs = extract_pitch(y, sr, fmin, fmax, frame_length, hop_length)
    voiced_count = int(np.sum(voiced_flag))
    print(f"  [3/8] pyin 提取: {len(f0)} 帧, 有声 {voiced_count} 帧 ({voiced_count/len(f0)*100:.1f}%)")

    # Step 4
    f0 = filter_voiced(f0, voiced_flag)
    print(f"  [4/8] 有声帧过滤完成")

    # Step 5
    f0 = median_filter_f0(f0, median_window)
    print(f"  [5/8] 中值滤波（窗口={median_window}）完成")

    # Step 6
    midi_seq = fix_octave_jumps(f0, max_jump)
    print(f"  [6/8] 跳变修正（> {max_jump} 半音）完成")

    # Step 7
    notes = merge_notes(midi_seq, hop_length, sr, merge_tolerance)
    print(f"  [7/8] 音符合并: {len(notes)} 个候选音符")

    # Step 8
    fmin_midi = freq_to_midi(fmin)
    fmax_midi = freq_to_midi(fmax)
    notes = filter_short_notes(notes, min_note_dur, fmin_midi, fmax_midi)
    short_dropped = len(notes)
    print(f"  [8/8] 碎音过滤（< {min_note_dur*1000:.0f}ms）: 保留 {len(notes)} 个音符")

    # 导出
    mid_path = os.path.join(output_dir, "melody_human.mid")
    csv_path = os.path.join(output_dir, "melody_human.csv")
    export_midi(notes, mid_path, sr)
    export_csv(notes, csv_path)

    # 统计
    if notes:
        durs = [n["duration"] for n in notes]
        midis = [n["midi"] for n in notes]
        short_rate = sum(1 for d in durs if d < 0.05) / len(notes) * 100
        print(f"\n[输出]: {mid_path}")
        print(f"   音符数: {len(notes)} | 碎音率(<50ms): {short_rate:.1f}%")
        print(f"   音域: {midi_to_note(min(midis))} ~ {midi_to_note(max(midis))}")
        print(f"   时长范围: {min(durs):.3f}s ~ {max(durs):.3f}s | 平均: {sum(durs)/len(durs):.3f}s")
    else:
        print(f"\n[警告] 未提取到有效音符，请检查输入或放宽参数")
    return notes


def main():
    ap = argparse.ArgumentParser(description="人声 WAV 转 MIDI（可听旋律线版）")
    ap.add_argument("input", help="输入 WAV 文件")
    ap.add_argument("-o", "--output", default=".", help="输出目录")
    ap.add_argument("--fmin", type=float, default=80.0, help="最低频率 Hz (默认80)")
    ap.add_argument("--fmax", type=float, default=800.0, help="最高频率 Hz (默认800)")
    ap.add_argument("--min-dur", type=float, default=0.08, help="最小音符时长 s (默认0.08)")
    ap.add_argument("--median-win", type=int, default=5, help="中值滤波窗口 (默认5)")
    ap.add_argument("--max-jump", type=int, default=7, help="跳变修正阈值半音 (默认7)")
    ap.add_argument("--merge-tol", type=int, default=1, help="合并容差半音 (默认1)")
    ap.add_argument("--hop", type=int, default=512, help="hop_length (默认512)")
    args = ap.parse_args()

    wav_to_midi(
        args.input, args.output,
        fmin=args.fmin, fmax=args.fmax,
        min_note_dur=args.min_dur, median_window=args.median_win,
        max_jump=args.max_jump, merge_tolerance=args.merge_tol,
        hop_length=args.hop,
    )


if __name__ == "__main__":
    main()