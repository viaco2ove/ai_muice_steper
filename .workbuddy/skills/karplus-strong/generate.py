#!/usr/bin/env python3
"""
 karplus 音频生成器 - 吉他合成器模式

用法:
    python generate.py <song> <track_id>
    python generate.py 走在 08_节奏吉他
    python generate.py 走在 08

输出到:
    workspace/project/{song}/song_engineer/track/ karplus/
    ├── {track_id}.json      # 中间 JSON
    └── {track_id}.wav       # 音频
"""

import os
import sys
import json
import argparse
from pathlib import Path

import numpy as np
import soundfile as sf

# ==================== 配置 ====================
PROJECT_DIR = Path(__file__).parent.parent.parent.parent
SAMPLE_RATE = 44100


def midi_to_freq(midi_note):
    """MIDI 音符转频率"""
    return 440.0 * (2.0 ** ((midi_note - 69) / 12.0))


def karplus_strong(frequency, duration, velocity=0.8, technique="pluck", decay_factor=0.996):
    """
    Karplus-Strong 物理建模合成器
    """
    n_samples = int(duration * SAMPLE_RATE)
    if n_samples <= 0:
        return np.array([])

    period = max(int(SAMPLE_RATE / frequency), 2)
    noise = np.random.randn(period) * velocity

    if technique == "slap":
        noise = np.concatenate([noise * 2, np.random.randn(period) * velocity * 0.5])
        period = len(noise)
        decay_factor = 0.990

    buffer = noise.copy()
    output = np.zeros(n_samples)

    for i in range(n_samples):
        output[i] = buffer[i % period]
        avg = (buffer[i % period] + buffer[(i + 1) % period]) / 2
        buffer[i % period] = avg * decay_factor

    t = np.linspace(0, duration, n_samples, endpoint=False)

    if technique == "slap":
        attack = np.exp(-t * 40)
        sustain = np.exp(-t * 15)
    else:
        attack = np.minimum(t * 80, 1.0)
        sustain = np.exp(-t * 2.5)

    envelope = attack * sustain

    if technique != "slap":
        string_noise = np.random.randn(n_samples) * 0.01 * np.exp(-t * 20)
        output = output * envelope + string_noise
    else:
        output = output * envelope

    output *= velocity
    return output


def generate_slap_guitar(frequency, duration, velocity=0.8):
    """拍弦吉他音色"""
    n_samples = int(duration * SAMPLE_RATE)
    t = np.linspace(0, duration, n_samples, endpoint=False)

    fundamental = np.sin(2 * np.pi * frequency * t)
    h2 = 0.4 * np.sin(2 * np.pi * frequency * 2 * t)
    h3 = 0.2 * np.sin(2 * np.pi * frequency * 3 * t)
    h4 = 0.1 * np.sin(2 * np.pi * frequency * 4 * t)
    noise = np.random.randn(n_samples) * 0.25

    attack = np.exp(-t * 60)
    decay = np.exp(-t * 12)

    signal = (fundamental + h2 + h3 + h4) * attack * decay * velocity * 0.7
    signal += noise * attack * 0.3

    return signal


def parse_beat_pos(beat_pos, tempo):
    """解析节拍位置为时间"""
    parts = beat_pos.split('.')
    measure = int(parts[0])
    beat = int(parts[1])
    subdiv = int(parts[2])

    beat_duration = 60.0 / tempo
    measure_duration = beat_duration * 4

    start_time = (measure - 1) * measure_duration + (beat - 1) * beat_duration
    start_time += (subdiv - 1) * beat_duration / 4

    return start_time


def parse_duration(duration_str, tempo):
    """解析持续时间"""
    beat_duration = 60.0 / tempo

    if "全全" in duration_str:
        return beat_duration * 8
    elif "全" in duration_str:
        return beat_duration * 4
    elif "2分" in duration_str:
        return beat_duration * 2
    elif "4分" in duration_str:
        return beat_duration
    elif "8分" in duration_str:
        return beat_duration / 2
    elif "16分" in duration_str:
        return beat_duration / 4
    elif "32分" in duration_str:
        return beat_duration / 8
    return beat_duration


def find_input_json(song, track_id):
    """
    查找输入 JSON 文件

    Args:
        song: 歌曲名 (如 "走在")
        track_id: 轨道ID (如 "08", "08_节奏吉他")

    Returns:
        Path: 原始 JSON 文件路径
    """
    track_dir = PROJECT_DIR / "workspace" / "project" / song / "song_engineer" / "track"

    if not track_dir.exists():
        raise FileNotFoundError(f"目录不存在: {track_dir}")

    # 清理 track_id
    track_id_clean = track_id.replace('.json', '')

    # 尝试精确匹配
    exact_path = track_dir / f"{track_id_clean}.json"
    if exact_path.exists():
        return exact_path

    # 尝试前缀匹配
    prefix_path = track_dir / f"{track_id_clean}_修正琶音2.json"
    if prefix_path.exists():
        return prefix_path

    # 模糊匹配
    for p in track_dir.glob(f"{track_id_clean}*.json"):
        if ' karplus' not in str(p):
            return p

    raise FileNotFoundError(f"找不到 {song}/{track_id} 的 JSON 文件")


def get_output_dir(song):
    """获取输出目录"""
    return PROJECT_DIR / "workspace" / "project" / song / "song_engineer" / "track" / " karplus"


def prepare_output_json(data, source_path, output_path):
    """
    准备输出 JSON 文件

    保留原始 notes 数组，只添加 schema 和元数据字段

    Args:
        data: 原始 JSON 数据
        source_path: 原始文件路径
        output_path: 输出 JSON 路径

    Returns:
        dict: 输出 JSON 数据
    """
    notes = data.get('notes', [])

    # 解析源文件名
    source_name = source_path.name

    # 技术统计
    techniques = {}
    for note in notes:
        tech = note.get('technique', '勾弦')
        techniques[tech] = techniques.get(tech, 0) + 1

    # 复制原始数据，添加 schema
    output_data = dict(data)  # 浅拷贝
    output_data['schema'] = 'track.guitar.synth.v1'
    output_data['source'] = source_name
    output_data['synthesizer'] = 'karplus_strong'
    output_data['reverb'] = 'simple_delay'

    return output_data, techniques


def generate_inputs_md(data, techniques, output_path):
    """
    生成  karplus 输入提示词文件

    Args:
        data: JSON 数据
        techniques: 技术统计 dict
        output_path: 输出路径
    """
    instrument = data.get('instrument', '木吉他')
    tempo = data.get('tempo', 68)
    name = data.get('name', '')

    # 乐器描述
    instrument_map = {
        '钢弦': 'acoustic steel string guitar',
        '尼龙': 'classical nylon guitar',
        '电吉他': 'electric guitar',
        '贝斯': 'bass guitar',
        '木吉他': 'acoustic guitar',
    }
    instrument_desc = 'acoustic guitar'
    for key, desc in instrument_map.items():
        if key in instrument:
            instrument_desc = desc
            break

    # 风格描述 - 根据主要技术
    main_technique = max(techniques.items(), key=lambda x: x[1])[0] if techniques else '勾弦'
    style_map = {
        '四勾': 'fingerpicking, gentle chord strumming',
        '5勾弦': 'full chord strumming, rich harmonics',
        '拍弦': 'percussive slap guitar, rhythmic groove',
        '琶音': 'arpeggio pattern, delicate picking',
        '勾弦': 'plucking, clean fingerpicking',
        '扫弦': 'aggressive strumming, powerful chords',
    }
    style_desc = style_map.get(main_technique, 'fingerpicking')

    # 速度描述
    if tempo < 70:
        tempo_desc = 'slow tempo ballad feel'
    elif tempo < 90:
        tempo_desc = 'moderate tempo'
    elif tempo < 120:
        tempo_desc = 'upbeat, energetic rhythm'
    else:
        tempo_desc = 'fast tempo, lively groove'

    # 情绪描述
    mood_map = {
        '节奏': 'warm, rhythmic groove',
        '主旋': 'melodic, lyrical',
        '分解': 'delicate, intricate',
        '独奏': 'solo performance feel',
        '和声': 'harmonic richness',
    }
    mood_desc = 'warm atmosphere'
    for key, desc in mood_map.items():
        if key in name:
            mood_desc = desc
            break

    # 组合提示词 - 纯文本
    prompt = f"{instrument_desc}, {style_desc}, {tempo_desc}, {mood_desc}"

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(prompt)


def generate_audio(data, output_wav_path, tempo):
    """
    生成音频

    Args:
        data: JSON 数据
        output_wav_path: 输出 WAV 路径
        tempo: BPM
    """
    notes = data.get('notes', [])

    # 计算总时长
    max_time = 0
    for note in notes:
        start_time = parse_beat_pos(note['beat_pos'], tempo)
        duration = parse_duration(note.get('duration', '4分'), tempo)
        max_time = max(max_time, start_time + duration)
    max_time += 2.0

    n_samples = int(max_time * SAMPLE_RATE)
    audio = np.zeros(n_samples)

    # 按时间排序
    sorted_notes = sorted(notes, key=lambda n: n['beat_pos'])

    print("  生成音频...")

    for i, note in enumerate(sorted_notes):
        technique = note.get('technique', '勾弦')
        midi = note.get('midi', 60)
        velocity = note.get('velocity', 64) / 127.0
        beat_pos = note['beat_pos']
        duration_str = note.get('duration', '4分')

        freq = midi_to_freq(midi)
        start_time = parse_beat_pos(beat_pos, tempo)
        duration = parse_duration(duration_str, tempo)

        start_sample = int(start_time * SAMPLE_RATE)

        if '拍弦' in technique:
            note_audio = generate_slap_guitar(freq, duration, velocity)
        elif '琶音' in technique:
            note_audio = karplus_strong(freq, duration * 0.7, velocity * 0.8, "pluck", 0.994)
        else:
            note_audio = karplus_strong(freq, duration, velocity, "pluck", 0.997)

        end_sample = start_sample + len(note_audio)

        if end_sample <= n_samples:
            fade_len = min(int(0.002 * SAMPLE_RATE), len(note_audio) // 4)
            if fade_len > 0:
                note_audio[:fade_len] *= np.linspace(0, 1, fade_len)
                note_audio[-fade_len:] *= np.linspace(1, 0, fade_len)
            audio[start_sample:end_sample] += note_audio

        if (i + 1) % 100 == 0:
            print(f"    处理中... {i + 1}/{len(notes)}")

    print("    完成!")

    # 归一化
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = audio / max_val * 0.85

    # 渐入渐出
    fade_samples = int(0.1 * SAMPLE_RATE)
    if fade_samples < len(audio):
        audio[:fade_samples] *= np.linspace(0, 1, fade_samples)
        audio[-fade_samples:] *= np.linspace(1, 0, fade_samples)

    # 混响
    print("  添加混响...")
    reverb_delay = int(0.025 * SAMPLE_RATE)
    reverb_decay = 0.25

    output = audio.copy()
    for d in [reverb_delay, reverb_delay * 2, reverb_delay * 3]:
        if d < len(output):
            delayed = np.zeros_like(output)
            delayed[d:] = output[:-d] * reverb_decay
            reverb_decay *= 0.6
            output += delayed

    # 最终归一化
    max_val = np.max(np.abs(output))
    if max_val > 0:
        output = output / max_val * 0.9

    # 保存
    output_wav_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_wav_path), output.astype(np.float32), SAMPLE_RATE)


def main():
    parser = argparse.ArgumentParser(description=' karplus 吉他合成器')
    parser.add_argument('song', help='歌曲名 (如 走在)')
    parser.add_argument('track_id', help='轨道ID (如 08, 08_节奏吉他)')
    parser.add_argument('--json-only', action='store_true', help='只生成 JSON')
    parser.add_argument('--wav-only', action='store_true', help='只生成 WAV')

    args = parser.parse_args()

    print("=" * 60)
    print(" karplus 吉他合成器")
    print("=" * 60)

    # 清理 track_id
    track_id_clean = args.track_id.replace('.json', '')

    # 查找输入文件
    print(f"\n📂 查找 {args.song}/{args.track_id}...")
    try:
        source_path = find_input_json(args.song, args.track_id)
        print(f"   找到: {source_path.name}")
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return 1

    # 加载数据
    with open(source_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 获取输出目录
    output_dir = get_output_dir(args.song)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 输出文件路径
    output_json_path = output_dir / f"{track_id_clean}.json"
    output_wav_path = output_dir / f"{track_id_clean}.wav"
    output_inputs_path = output_dir / f"{track_id_clean}.inputs.md"

    # 1. 生成 JSON 和 inputs.md
    if not args.wav_only:
        print(f"\n📝 生成输出 JSON...")
        output_json_data, techniques = prepare_output_json(data, source_path, output_json_path)

        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(output_json_data, f, ensure_ascii=False, indent=2)

        print(f"   ✅ 已保存: {output_json_path}")

        # 生成 inputs.md
        print(f"\n📄 生成  karplus 输入提示词...")
        generate_inputs_md(data, techniques, output_inputs_path)
        print(f"   ✅ 已保存: {output_inputs_path}")

    # 2. 生成 WAV
    if not args.json_only:
        print(f"\n🎵 生成音频...")
        tempo = data.get('tempo', data.get('BPM', 68))
        generate_audio(data, output_wav_path, tempo)

        print(f"   ✅ 已保存: {output_wav_path}")
        print(f"   大小: {output_wav_path.stat().st_size / 1024 / 1024:.1f} MB")

    print("\n" + "=" * 60)
    print("完成!")
    print("=" * 60)

    return 0


if __name__ == '__main__':
    sys.exit(main())