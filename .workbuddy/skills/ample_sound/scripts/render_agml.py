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
    
    notes = data.get("notes", [])
    tempo = data.get("tempo", 68)
    beat_duration = 60.0 / tempo
    
    # 3. 计算节拍位置并按时间分组
    notes = process_notes_for_arp(notes, tempo)
    time_groups = group_notes_by_time(notes)
    
    # 4. 创建输出目录
    output_dir = PROJECT_DIR / "workspace" / "project" / song / "song_engineer" / "track" / "ample_sound"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not args.json_only:
        engine = daw.RenderEngine(SAMPLE_RATE, BUFFER_SIZE)
        try:
            guitar = engine.make_plugin_processor("AmpleGuitar", VST_PATH)
        except Exception as e:
            print(f"    ❌ VST3 加载失败: {e}")
            sys.exit(1)

        # ═══ 单次渲染：预热段 + 真实段一起加入，渲染后裁掉预热段 ═══
        # 预热段：用前几个音符在 0~WARMUP_OFFSET 内把 VST 状态"唤醒"，
        # 但这段音频最终会被裁掉，不会出现在输出 wav 里。
        WARMUP_OFFSET = 5.5
        sorted_times = sorted(time_groups.keys())

        # 预热音符：铺在 0 ~ WARMUP_OFFSET-0.5 之间（留 0.5s 间隙让尾音自然衰减）
        warmup_times = sorted_times[:5]
        if warmup_times:
            warmup_span = max(0.1, WARMUP_OFFSET - 0.5)
            step = warmup_span / max(1, len(warmup_times))
            for i, t in enumerate(warmup_times):
                wt = i * step
                for note in time_groups[t]:
                    guitar.add_midi_note(note.get("midi", 60), note.get("velocity", 80), wt, 0.5)

        # 真实音符：从 WARMUP_OFFSET 开始
        index =1
        for t in sorted_times:
            print(f"### 同一个时间的音素 {index}### ")
            index = index + 1
            group = time_groups[t]
            is_slap = any(n.get("technique") == "拍弦" for n in group)

            if is_slap:
                # 纯净的拍弦 FX 音效（不再有低音闷响，也不会出现长度为 0 的报错）
                slap_vel_voice = 127
                # 比较坑的地方是 5 ~ 6 区，中间隐藏了一堆高频键位。
                # 实际到了89 才是音效区。89 是弦摩擦音换和弦等时加入可以增加真实感，90 是拍弦音
                fx_midi = 90  # 可根据喜好在 90~100 之间调整
                guitar.add_midi_note(fx_midi, slap_vel_voice, t + WARMUP_OFFSET - 0.01, 0.5)
                print(f"      拍弦 t={t + WARMUP_OFFSET:.3f}s, midi={fx_midi}, slap_vel_voice={slap_vel_voice}")
            # 按音高排序并过滤占位符
            group_sorted = sorted(group, key=lambda x: x.get("midi", 60))
            valid_notes = [n for n in group_sorted if n.get("technique") != "拍弦"]
            note_count = len(valid_notes)

            for valid_idx, note in enumerate(valid_notes):
                technique = note.get("technique", "勾弦")
                midi = note.get("midi", 60)
                velocity = note.get("velocity", 80)
                duration = parse_duration(note.get("duration", "4分"), tempo)

                human_vel = min(127, max(1, int(velocity * VELOCITY_BOOST) + random.randint(-5, 5)))

                # 如果当前拍有拍弦，将正常的弦音音效压制，凸显拍弦感
                if is_slap:
                    human_vel = max(1, int(human_vel * 0.3))

                # 技法时长与延迟微调
                if technique == "琶音":
                    arp_total_time = min(0.3, beat_duration * 0.4)
                    arp_delay = arp_total_time / max(1, note_count - 1)
                    delay = valid_idx * arp_delay
                    final_duration = duration * 1.6
                    print(f"     琶音 delay={delay}")
                elif "勾" in technique:
                    delay = random.uniform(-0.003, 0.003)
                    final_duration = duration * 1.3
                    print(f"     勾 delay={delay}")
                else:
                    delay = valid_idx * STRUM_DELAY
                    final_duration = duration * 1.3

                human_start = t + WARMUP_OFFSET + delay

                tech_key = TECH_TO_KEYSWITCH.get(technique, None)
                if tech_key:
                    ks_note = KEYSWITCH[tech_key]
                    guitar.add_midi_note(ks_note, 127, human_start - 0.005, 0.01)
                    print(f"     弹奏{technique} t={human_start - 0.005:.3f}s, midi={ks_note}, human_vel={127}, final_duration={final_duration}")
                guitar.add_midi_note(midi, human_vel, human_start, final_duration)
                print( f"     弹奏{technique} t={human_start:.3f}s, midi={midi}, human_vel={human_vel}, final_duration={final_duration}")
        # 计算总时长（含预热段）并一次性渲染
        max_time = WARMUP_OFFSET  # 至少包含预热段
        if sorted_times:
            max_time = max(max_time, max(sorted_times) + WARMUP_OFFSET)
        for note in notes:
            dur = parse_duration(note.get("duration", "4分"), tempo)
            max_time = max(max_time, note["_adjusted_start"] + WARMUP_OFFSET + dur * 1.5)

        engine.load_graph([(guitar, [])])
        engine.render(max_time + 2.0)

        # ═══ 裁掉预热段：只保留 WARMUP_OFFSET 之后的音频 ═══
        # 注意：必须 copy，否则原地 *= 淡入淡出可能不生效
        audio_data = np.array(engine.get_audio(), copy=True)  # (channels, samples)
        warmup_samples = int(WARMUP_OFFSET * SAMPLE_RATE)
        if audio_data.ndim == 2:
            trimmed = audio_data[:, warmup_samples:]
        else:
            trimmed = audio_data[warmup_samples:]

        # 末尾再加一点淡出，避免最后一下硬切
        tail = min(int(0.05 * SAMPLE_RATE), trimmed.shape[-1] // 4)
        if tail > 0:
            fade = np.linspace(1.0, 0.0, tail)
            if trimmed.ndim == 2:
                trimmed[:, -tail:] *= fade
            else:
                trimmed[-tail:] *= fade

        # 开头也做一个小淡入，防止第一采样点杂音
        head = min(int(0.01 * SAMPLE_RATE), trimmed.shape[-1] // 4)
        if head > 0:
            fade_in = np.linspace(0.0, 1.0, head)
            if trimmed.ndim == 2:
                trimmed[:, :head] *= fade_in
            else:
                trimmed[:head] *= fade_in

        # 保存音频
        output_wav = output_dir / f"{track_id_clean}.wav"
        import tempfile
        import shutil
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        sf.write(tmp_path, trimmed.T if trimmed.ndim == 2 else trimmed, SAMPLE_RATE)
        if output_wav.exists():
            try: output_wav.unlink()
            except PermissionError: pass
        shutil.copy2(tmp_path, str(output_wav))
        Path(tmp_path).unlink()
        print(f"    ✅ 音频已保存(已裁预热段): {output_wav}")
    
    # 5. 生成元数据 JSON
    if not args.wav_only:
        output_json = output_dir / f"{track_id_clean}.json"
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
