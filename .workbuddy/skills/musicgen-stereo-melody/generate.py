#!/usr/bin/env python3
"""
MusicGen 音频生成器 - 真正使用 HuggingFace MusicGen 模型

用法:
    python generate.py <song> <track_id>
    python generate.py 走在 08_节奏吉他
"""

import os
import sys
import json
import argparse
from pathlib import Path

# 设置 HuggingFace 缓存路径
os.environ['HF_HOME'] = 'C:/Users/viaco/.cache/huggingface'
os.environ['TRANSFORMERS_OFFLINE'] = '0'

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
SAMPLE_RATE = 32000  # MusicGen 固定采样率


def load_track_json(song, track_id):
    """加载轨道 JSON 文件"""
    base_path = Path(__file__).parent.parent.parent.parent / 'workspace' / 'project' / song / 'song_engineer' / 'track'
    
    if not base_path.exists():
        raise FileNotFoundError(f"目录不存在: {base_path}")
    
    json_files = list(base_path.glob(f'{track_id}*.json'))
    json_files = [f for f in json_files if 'musicgen' not in str(f)]
    
    if not json_files:
        raise FileNotFoundError(f"找不到 {song}/{track_id} 的 JSON 文件")
    
    json_path = json_files[0]
    print(f"📂 找到: {json_path}")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f), json_path


def prepare_json_for_generation(data, song, track_id):
    """准备用于生成的 JSON 文件"""
    track_id_num = data.get('track_id', 0)
    name = data.get('name', '')
    instrument = data.get('instrument', '木吉他')
    tempo = data.get('tempo', data.get('BPM', 68))
    volume = data.get('volume', 0.4)
    
    prepared_notes = []
    for note in data.get('notes', []):
        prepared_note = {
            'actual': note.get('actual', ''),
            'midi': note.get('midi', 60),
            'beat_pos': note.get('beat_pos', '1.1.1'),
            'velocity': note.get('velocity', 80),
            'technique': note.get('technique', 'pluck'),
        }
        
        duration = note.get('duration', '4分')
        if isinstance(duration, str):
            prepared_note['duration'] = duration
        else:
            prepared_note['duration'] = '4分'
        
        if 'sustain_beats' in note:
            prepared_note['sustain_beats'] = note['sustain_beats']
        
        prepared_notes.append(prepared_note)
    
    output_data = {
        'schema': 'track.guitar.v1',
        'track_id': track_id_num,
        'name': name,
        'instrument': instrument,
        'tempo': tempo,
        'volume': volume,
        'notes': prepared_notes
    }
    
    return output_data


def json_to_musicgen_prompt(data):
    """
    将 JSON 数据转换为 MusicGen 文本描述
    
    注意：MusicGen 是生成模型，不是合成器。
    它根据文本描述生成音乐，不能精确控制每个音符。
    """
    instrument = data.get('instrument', '木吉他')
    tempo = data.get('tempo', 68)
    notes = data.get('notes', [])
    
    # 分析曲目特点
    has_arp = any('琶音' in n.get('technique', '') for n in notes)
    has_slap = any('拍弦' in n.get('technique', '') for n in notes)
    has_pluck = any('勾弦' in n.get('technique', '') for n in notes)
    
    # 统计段落
    bars = set()
    for n in notes:
        bp = n.get('beat_pos', '1.1.1')
        bar = int(bp.split('.')[0])
        bars.add(bar)
    total_bars = max(bars) if bars else 52
    
    # 构建描述
    prompt_parts = []
    
    # 乐器
    if '钢弦' in instrument:
        prompt_parts.append("steel string acoustic guitar")
    elif '尼龙' in instrument:
        prompt_parts.append("nylon string classical guitar")
    else:
        prompt_parts.append("acoustic guitar")
    
    # 演奏技巧
    techniques = []
    if has_arp:
        techniques.append("fingerpicked arpeggios")
    if has_slap:
        techniques.append("percussive strumming")
    if has_pluck:
        techniques.append("gentle fingerpicking")
    if not techniques:
        techniques.append("rhythmic strumming")
    
    prompt_parts.append(', '.join(techniques))
    
    # 风格
    prompt_parts.append("warm tone")
    prompt_parts.append("natural decay")
    
    # 速度和时长
    if tempo < 70:
        prompt_parts.append("slow ballad tempo")
    elif tempo < 90:
        prompt_parts.append("moderate tempo")
    else:
        prompt_parts.append("upbeat tempo")
    
    prompt_parts.append(f"approximately {total_bars * 4} seconds duration")
    
    # 氛围
    prompt_parts.append("intimate acoustic recording")
    prompt_parts.append("soft dynamics")
    
    return '. '.join(prompt_parts)


def generate_with_musicgen(prompt, model_name, duration_seconds=30):
    """
    使用 MusicGen 模型生成音频
    
    Args:
        prompt: 文本描述
        model_name: 模型名称
        duration_seconds: 生成时长（秒）
    
    Returns:
        numpy array: 音频数据 (stereo)
    """
    print(f"🔄 加载模型: {model_name}...")
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"   设备: {device}")
    
    # 加载模型
    processor = AutoProcessor.from_pretrained(model_name)
    model = MusicgenMelodyForConditionalGeneration.from_pretrained(model_name)
    model = model.to(device)
    
    print(f"✅ 模型加载完成")
    print(f"📝 描述: {prompt[:100]}...")
    
    # 准备输入
    inputs = processor(text=[prompt], padding=True, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}
    
    # 计算 token 数量（约 50 tokens/秒）
    max_new_tokens = int(duration_seconds * 50)
    
    print(f"🎵 正在生成 {duration_seconds} 秒音频...")
    
    # 生成
    audio_values = model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        guidance_scale=3.0,
        do_sample=True,
    )
    
    # 转换为 numpy
    audio = audio_values[0].cpu().float().numpy()
    
    print(f"✅ 生成完成!")
    print(f"   形状: {audio.shape} (channels, samples)")
    print(f"   时长: {audio.shape[1]/SAMPLE_RATE:.1f} 秒")
    
    return audio


def generate_from_json(data, output_wav_path, model_name):
    """
    从 JSON 数据使用 MusicGen 生成音频
    """
    print(f"\n🎵 使用 MusicGen 生成音频...")
    
    # 转换为文本描述
    prompt = json_to_musicgen_prompt(data)
    
    # 计算时长（从 JSON 中估算）
    tempo = data.get('tempo', 68)
    notes = data.get('notes', [])
    
    if notes:
        max_bar = max(int(n.get('beat_pos', '1.1.1').split('.')[0]) for n in notes)
        # 每小节4拍，每拍60/tempo秒
        estimated_duration = min(max_bar * 4 * 60 / tempo, 60)  # 最多60秒
    else:
        estimated_duration = 30
    
    estimated_duration = max(10, min(estimated_duration, 60))  # 限制在 10-60 秒
    
    print(f"   估算时长: {estimated_duration:.0f} 秒")
    
    # 生成
    audio = generate_with_musicgen(prompt, model_name, estimated_duration)
    
    # 转置为 (samples, channels) 用于保存
    audio = audio.T
    
    # 保存
    os.makedirs(os.path.dirname(output_wav_path), exist_ok=True)
    sf.write(output_wav_path, audio, SAMPLE_RATE)
    
    print(f"✅ 已保存: {output_wav_path}")
    print(f"   大小: {os.path.getsize(output_wav_path)/1024/1024:.2f} MB")


def main():
    parser = argparse.ArgumentParser(description='MusicGen 音频生成器')
    parser.add_argument('song', help='歌曲名 (如 走在)')
    parser.add_argument('track_id', help='轨道ID (如 08_节奏吉他)')
    parser.add_argument('--model', '-m', default=DEFAULT_MODEL, help=f'MusicGen 模型')
    parser.add_argument('--json-only', action='store_true', help='只生成 JSON')
    parser.add_argument('--wav-only', action='store_true', help='只生成 WAV')
    parser.add_argument('--duration', '-d', type=int, default=0, help='生成时长（秒）')
    
    args = parser.parse_args()
    
    # 加载原始 JSON
    print(f"📂 加载 {args.song}/{args.track_id}...")
    data, json_path = load_track_json(args.song, args.track_id)
    
    # 确定输出目录
    base_path = json_path.parent
    musicgen_dir = base_path / 'musicgen'
    musicgen_dir.mkdir(exist_ok=True)
    
    track_id_clean = args.track_id.replace('.json', '')
    output_json_path = musicgen_dir / f'{track_id_clean}.json'
    output_wav_path = musicgen_dir / f'{track_id_clean}.wav'
    
    # 1. 生成可用 JSON
    if not args.wav_only:
        print(f"\n📝 生成可用 JSON...")
        output_data = prepare_json_for_generation(data, args.song, track_id_clean)
        
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 已保存: {output_json_path}")
    
    # 2. 生成 WAV（使用 MusicGen）
    if not args.json_only:
        if not args.wav_only:
            with open(output_json_path, 'r', encoding='utf-8') as f:
                generation_data = json.load(f)
        else:
            generation_data = prepare_json_for_generation(data, args.song, track_id_clean)
        
        generate_from_json(generation_data, str(output_wav_path), args.model)


if __name__ == '__main__':
    main()
