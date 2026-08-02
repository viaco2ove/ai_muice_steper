"""
Ample Sound 吉他音轨渲染脚本 v7.1 (指弹修复版)
使用 dawdreamer + Ample Guitar M Lite VST3
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import argparse
import json
import os
import random
from pathlib import Path
from collections import defaultdict

import dawdreamer as daw
import soundfile as sf
import numpy as np

# ==================== 配置 ====================
PROJECT_DIR = Path(__file__).parent.parent.parent.parent.parent
SAMPLE_RATE = 44100
BUFFER_SIZE = 512

# VST3 路径
VST_PATH = "C:/Program Files/Common Files/VST3/AGML.vst3"

# 吉他参数
STRUM_DELAY = 0.018       # 普通扫弦逐弦时差（秒）
VELOCITY_BOOST = 1.10     # 力度增强系数

# KeySwitch 映射
KEYSWITCH = {
    "normal": 12,         # C0 - Sustain
    "harmonics": 13,       # C#0 - Natural Harmonic
    "palm_mute": 14,       # D0 - Palm Mute
    "slide": 15,           # D#0 - Slide In/Out
    "legato_slide": 16,    # E0 - Legato Slide
    "hammer_pull": 17,     # F0 - Hammer-On & Pull-Off
    "slide_guitar": 18,    # F#0 - Slide Guitar
    "tap": 19,             # G0 - 保留
}

TECH_TO_KEYSWITCH = {
    "闷音": "palm_mute",
    "泛音": "harmonics",
    "点弦": "tap",
    "滑音": "slide",
    "连奏滑音": "legato_slide",
    "击勾弦": "hammer_pull",
}


def parse_beat_pos(beat_pos, tempo=68):
    """解析 beat_pos 格式 '小节.拍.十六分'，返回秒"""
    parts = beat_pos.split(".")
    if len(parts) < 2:
        return 0.0
    bar = int(parts[0])
    beat = int(parts[1])
    sub = int(parts[2]) if len(parts) > 2 else 1
    beat_duration = 60.0 / tempo
    bar_duration = beat_duration * 4
    sub_duration = beat_duration / 4
    seconds = (bar - 1) * bar_duration + (beat - 1) * beat_duration + (sub - 1) * sub_duration
    return seconds


def parse_duration(duration_str, tempo=68):
    """解析中文时值，返回秒"""
    beat_duration = 60.0 / tempo
    mapping = {
        "全": beat_duration * 4,
        "2分": beat_duration * 2,
        "4分": beat_duration,
        "8分": beat_duration / 2,
        "16分": beat_duration / 4,
        "32分": beat_duration / 8,
    }
    return mapping.get(duration_str, beat_duration)


def find_input_json(song, track_id):
    """查找输入 JSON 文件"""
    track_dir = PROJECT_DIR / "workspace" / "project" / song / "song_engineer" / "track"
    track_id_clean = track_id.replace(".json", "")
    exact = track_dir / f"{track_id_clean}.json"
    if exact.exists():
        return exact
    prefix_matches = sorted(track_dir.glob(f"{track_id_clean}*.json"))
    if prefix_matches:
        return prefix_matches[-1]
    return None


def process_notes_for_arp(notes, tempo):
    """处理琶音音符：保持原节拍位置。"""
    processed = []
    for note in notes:
        note = dict(note)
        note["_adjusted_start"] = parse_beat_pos(note["beat_pos"], tempo)
        processed.append(note)
    return processed


def group_notes_by_time(notes):
    """将音符按开始时间分组"""
    time_groups = defaultdict(list)
    for note in notes:
        t = round(note["_adjusted_start"], 3)
        time_groups[t].append(note)
    return time_groups


def main():
    parser = argparse.ArgumentParser(description="Ample Sound 吉他渲染 v7.1")
    parser.add_argument("song", help="歌曲名")
    parser.add_argument("track_id", help="轨道ID，如 08_节奏吉他")
    parser.add_argument("--wav-only", action="store_true", help="只生成 WAV")
    parser.add_argument("--json-only", action="store_true", help="只生成 JSON")
    args = parser.parse_args()
    
    song = args.song
    track_id = args.track_id
    track_id_clean = track_id.replace(".json", "")
    
    print("=" * 60)
    print(f"Ample Sound 渲染 v7.1 - {song} / {track_id_clean}")
    print("=" * 60)
    
    # 1. 查找输入文件
    input_path = find_input_json(song, track_id)
    if not input_path:
        print(f"    ❌ 未找到输入文件")
        sys.exit(1)


    # 2. 读取数据
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 4. 创建输出目录
    output_dir = PROJECT_DIR / "workspace" / "project" / song / "song_engineer" / "track" / "ample_sound"
    output_dir.mkdir(parents=True, exist_ok=True)
    tempo = data.get("tempo", 68)
    
    # 5. 生成元数据 JSON
    if not args.wav_only:
        output_json = output_dir / f"{track_id_clean}.conf.json"
        output_data = {
            "schema": "track.ample_sound.v1",
            "track_id": data.get("track_id", 8),
            "name": data.get("name", track_id_clean),
            "tempo": tempo,
            "source": input_path.name,
            "renderer": "dawdreamer_v7.1"
        }
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"    ✅ JSON 已保存: {output_json}")

if __name__ == "__main__":
    main()
