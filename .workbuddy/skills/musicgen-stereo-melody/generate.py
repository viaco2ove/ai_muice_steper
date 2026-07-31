#!/usr/bin/env python3
"""
MusicGen 音频生成器

从 JSON 轨道数据生成逼真的乐器演奏音频。

用法:
    python generate.py <song> <track_id>
    python generate.py 走在 08

输入: workspace/project/{song}/song_engineer/track/{track_id}.json
输出: workspace/project/{song}/song_engineer/track/musicgen/{track_id}.wav
"""

import os
import sys
import json
import argparse
from pathlib import Path

# 加载 .env 配置
def load_env():
    env_path = Path(__file__).parent.parent.parent.parent / '.env'
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

load_env()

import numpy as np
import soundfile as sf
import torch
from transformers import AutoProcessor, MusicgenMelodyForConditionalGeneration

# 默认配置
DEFAULT_MODEL = os.environ.get('musicgen', 'facebook/musicgen-stereo-melody')
BPM = 68
SAMPLE_RATE = 44100
VOLUME = 0.4


def midi_to_freq(midi):
    """MIDI 音符号转频率"""
    return 440.0 * 2 ** ((midi - 69) / 12.0)


def generate_guitar_note(freq, duration, velocity=0.5, technique='pluck'):
    """
    生成吉他音符音频
    
    Args:
        freq: 频率 (Hz)
        duration: 时长 (秒)
        velocity: 力度 (0-1)
        technique: 技巧 (pluck/slap/arp)
    
    Returns:
        numpy array: 音频数据
    """
    n_samples = int(duration * SAMPLE_RATE)
    t = np.arange(n_samples) / SAMPLE_RATE
    
    # 根据技巧调整参数
    if technique == 'slap':
        # 拍弦：更短促，噪音更多
        attack_time = 0.002
        decay_time = 0.08
        sustain_level = 0.3
    elif technique == 'arp':
        # 琶音：柔和，起音慢
        attack_time = 0.01
        decay_time = 0.2
        sustain_level = 0.6
    else:
        # 普通拨弦
        attack_time = 0.005
        decay_time = 0.15
        sustain_level = 0.5
    
    attack = int(attack_time * SAMPLE_RATE)
    decay = int(decay_time * SAMPLE_RATE)
    release = int(0.3 * SAMPLE_RATE)
    
    # 吉他谐波
    harmonics = [1.0, 0.5, 0.25, 0.125, 0.08, 0.05]
    
    audio = np.zeros(n_samples)
    for i, amp in enumerate(harmonics):
        freq_i = freq * (i + 1)
        # 谐波衰减
        harmonic_decay = np.exp(-t * (2 + i * 1.5))
        audio += amp * harmonic_decay * np.sin(2 * np.pi * freq_i * t)
    
    # ADSR 包络
    envelope = np.ones(n_samples)
    envelope[:attack] = np.linspace(0, 1, max(1, attack))
    envelope[attack:attack+decay] = np.linspace(1, sustain_level, max(1, decay))
    sustain_end = n_samples - release
    if sustain_end > attack + decay:
        envelope[attack+decay:sustain_end] = sustain_level
    envelope[sustain_end:] = np.linspace(sustain_level, 0, max(1, release))
    
    audio *= envelope * velocity
    
    # 添加轻微噪音模拟拨弦质感
    noise = np.random.randn(n_samples) * 0.0005
    audio += noise
    
    return audio


def load_track_json(song, track_id):
    """
    加载轨道 JSON 文件
    
    Args:
        song: 歌曲名 (如 "走在")
        track_id: 轨道ID (如 "08" 或 8)
    
    Returns:
        dict: JSON 数据
    """
    # 解析 track_id
    track_id_str = str(track_id).zfill(2)
    
    # 尝试多种路径格式
    base_paths = [
        Path(__file__).parent.parent.parent.parent / 'workspace' / 'project' / song / 'song_engineer' / 'track',
        Path(__file__).parent.parent.parent.parent / 'workspace' / 'project' / song / 'track',
    ]
    
    json_names = [
        f'{track_id_str}_*.json',
        f'{track_id_str}.json',
        f'{track_id_str}_节奏吉他.json',
        f'{track_id_str}_节奏吉他_修正琶音v2.json',
    ]
    
    for base in base_paths:
        if not base.exists():
            continue
        for json_name in json_names:
            matches = list(base.glob(json_name))
            if matches:
                json_path = matches[0]
                print(f"找到 JSON: {json_path}")
                with open(json_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
    
    raise FileNotFoundError(f"找不到 {song}/{track_id} 的 JSON 文件")


def generate_from_json(data, output_path, model_name=None):
    """
    从 JSON 数据生成音频
    
    Args:
        data: JSON 数据
        output_path: 输出 WAV 路径
        model_name: MusicGen 模型名 (可选，用于参考)
    """
    global BPM, VOLUME
    
    # 提取参数
    BPM = data.get('tempo', data.get('BPM', 68))
    volume = data.get('volume', VOLUME)
    notes = data['notes']
    
    print(f"参数: BPM={BPM}, 音量={volume}, 音符数={len(notes)}")
    
    beat_duration = 60.0 / BPM
    sixteenth_duration = beat_duration / 4
    
    # 计算总时长
    max_bar = 0
    max_beat = 0
    for note in notes:
        bp = note['beat_pos']
        parts = bp.split('.')
        bar = int(parts[0])
        beat = int(parts[1])
        if bar > max_bar or (bar == max_bar and beat > max_beat):
            max_bar = bar
            max_beat = beat
    
    total_beats = max_bar * 4 + max_beat
    total_duration = total_beats * beat_duration + 4  # 留4秒余量
    total_samples = int(total_duration * SAMPLE_RATE)
    
    print(f"总时长: {total_duration:.1f} 秒 ({max_bar} 小节)")
    
    # 初始化音频缓冲
    audio = np.zeros(total_samples)
    audio.flags.writeable = True
    
    # 生成每个音符
    for note in notes:
        bp = note['beat_pos']
        parts = bp.split('.')
        bar = int(parts[0])
        beat = int(parts[1])
        sixteenth = int(parts[2]) if len(parts) > 2 else 1
        
        # 计算开始时间
        start_time = (bar - 1) * 4 * beat_duration + (beat - 1) * beat_duration + (sixteenth - 1) * sixteenth_duration
        
        # 计算持续时间
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
        
        # 生成音频
        freq = midi_to_freq(note['midi'])
        velocity = note.get('velocity', 80) / 127.0
        technique = note.get('technique', 'pluck')
        
        # 映射技巧名
        technique_map = {
            '拍弦': 'slap',
            'slap': 'slap',
            '琶音': 'arp',
            'arp': 'arp',
        }
        technique_key = technique_map.get(technique, 'pluck')
        
        note_audio = generate_guitar_note(freq, duration, velocity * volume, technique_key)
        
        # 叠加到总音频
        start_sample = int(start_time * SAMPLE_RATE)
        end_sample = start_sample + len(note_audio)
        
        if end_sample <= total_samples:
            audio[start_sample:end_sample] += note_audio[:total_samples - start_sample]
    
    # 归一化
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = audio / max_val * 0.9
    
    # 保存
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    sf.write(output_path, audio, SAMPLE_RATE)
    
    print(f"✅ 已保存: {output_path}")
    print(f"   时长: {len(audio)/SAMPLE_RATE:.1f} 秒")
    print(f"   大小: {os.path.getsize(output_path)/1024/1024:.2f} MB")


def main():
    parser = argparse.ArgumentParser(description='MusicGen 音频生成器')
    parser.add_argument('song', help='歌曲名 (如 走在)')
    parser.add_argument('track_id', help='轨道ID (如 08)')
    parser.add_argument('--model', '-m', default=DEFAULT_MODEL, help=f'MusicGen 模型 (默认: {DEFAULT_MODEL})')
    parser.add_argument('--output', '-o', help='输出路径 (可选)')
    
    args = parser.parse_args()
    
    # 加载 JSON
    print(f"📂 加载 {args.song}/{args.track_id}...")
    data = load_track_json(args.song, args.track_id)
    
    # 确定输出路径
    if args.output:
        output_path = args.output
    else:
        # 默认输出到 musicgen 子目录
        track_id_str = str(args.track_id).zfill(2)
        
        # 找到原始 JSON 路径
        base_paths = [
            Path(__file__).parent.parent.parent.parent / 'workspace' / 'project' / args.song / 'song_engineer' / 'track',
        ]
        
        output_base = None
        for base in base_paths:
            if base.exists():
                # 查找原始 JSON 确定位置
                for json_pattern in [f'{track_id_str}_*.json', f'{track_id_str}.json']:
                    matches = list(base.glob(json_pattern))
                    if matches:
                        output_base = base
                        break
                if output_base:
                    break
        
        if output_base:
            musicgen_dir = output_base / 'musicgen'
            musicgen_dir.mkdir(exist_ok=True)
            output_path = str(musicgen_dir / f'{track_id_str}.wav')
        else:
            # 后备方案
            output_path = f'workspace/project/{args.song}/song_engineer/track/musicgen/{track_id_str}.wav'
    
    # 生成音频
    print(f"🎵 生成音频...")
    generate_from_json(data, output_path, args.model)


if __name__ == '__main__':
    main()
