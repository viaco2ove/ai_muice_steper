#!/usr/bin/env python3
"""生成修正后的节奏吉他音频"""
import json
import numpy as np
import soundfile as sf
import os

# 读取修正后的JSON
json_path = r'/workspace/project/走在/song_engineer/track/08_节奏吉他_修正琶音v2.json'
with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"音符数: {len(data['notes'])}")

# 参数
BPM = 68
SAMPLE_RATE = 44100
VOLUME = 0.4

beat_duration = 60.0 / BPM
sixteenth_duration = beat_duration / 4

def midi_to_freq(midi):
    return 440.0 * 2 ** ((midi - 69) / 12.0)

def generate_guitar_note(freq, duration, velocity=0.5, technique='pluck'):
    """生成吉他音符"""
    n_samples = int(duration * SAMPLE_RATE)
    t = np.arange(n_samples) / SAMPLE_RATE
    
    # 包络
    attack = int(0.005 * SAMPLE_RATE)
    decay = int(0.1 * SAMPLE_RATE)
    sustain_level = 0.7
    release = int(0.3 * SAMPLE_RATE)
    
    # 谐波（吉他音色）
    harmonics = [1.0, 0.5, 0.25, 0.125, 0.08]
    
    audio = np.zeros(n_samples)
    for i, amp in enumerate(harmonics):
        freq_i = freq * (i + 1)
        harmonic_decay = np.exp(-t * (3 + i * 2))
        audio += amp * harmonic_decay * np.sin(2 * np.pi * freq_i * t)
    
    # 包络
    envelope = np.ones(n_samples)
    envelope[:attack] = np.linspace(0, 1, attack)
    envelope[attack:attack+decay] = np.linspace(1, sustain_level, decay)
    sustain_end = n_samples - release
    envelope[attack+decay:sustain_end] = sustain_level
    envelope[sustain_end:] = np.linspace(sustain_level, 0, release)
    
    audio *= envelope * velocity
    noise = np.random.randn(n_samples) * 0.001
    audio += noise
    
    return audio

# 生成音频
total_beats = 52 * 4
total_duration = total_beats * beat_duration
total_samples = int(total_duration * SAMPLE_RATE) + int(beat_duration * 4)

audio = np.zeros(total_samples)
audio.flags.writeable = True

print("生成音频...")

for note in data['notes']:
    bp = note['beat_pos']
    parts = bp.split('.')
    bar = int(parts[0])
    beat = int(parts[1])
    sixteenth = int(parts[2])
    
    start_time = (bar - 1) * 4 * beat_duration + (beat - 1) * beat_duration + (sixteenth - 1) * sixteenth_duration
    
    if 'sustain_beats' in note:
        duration = (note['sustain_beats'] + 1) * beat_duration
    else:
        duration_str = note.get('duration', '8分')
        if '8分' in duration_str:
            duration = beat_duration / 2
        elif '4分' in duration_str:
            duration = beat_duration
        else:
            duration = beat_duration / 4
    
    freq = midi_to_freq(note['midi'])
    velocity = note.get('velocity', 80) / 127.0
    technique = note.get('technique', 'pluck')
    
    note_audio = generate_guitar_note(freq, duration, velocity * VOLUME, technique)
    
    start_sample = int(start_time * SAMPLE_RATE)
    end_sample = start_sample + len(note_audio)
    
    if end_sample <= total_samples:
        audio[start_sample:end_sample] += note_audio[:total_samples - start_sample]

# 归一化
max_val = np.max(np.abs(audio))
if max_val > 0:
    audio = audio / max_val * 0.9

# 保存
output_path = r'/workspace/project/走在/song_engineer/track/output/08_节奏吉他_修正版.wav'
os.makedirs(os.path.dirname(output_path), exist_ok=True)
sf.write(output_path, audio, SAMPLE_RATE)

print(f"\n✅ 音频已生成!")
print(f"   文件: {output_path}")
print(f"   时长: {len(audio)/SAMPLE_RATE:.1f} 秒")
print(f"   大小: {os.path.getsize(output_path)/1024/1024:.2f} MB")