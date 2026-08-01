"""
Ample Sound 吉他音轨渲染脚本 v7 (指弹技法修复版)
使用 dawdreamer + Ample Guitar M Lite VST3

修复点（相比 v6）：
1. 修复拍弦吞音：移除全局 continue，让同节拍的"四勾"正常发声
2. 修复勾弦生硬：识别"5勾弦"和"四勾"，消除逐弦延迟（仅保留 ±3ms 人感误差）
3. 修复琶音急促：根据当前 BPM 动态分配逐弦间距，让音符铺满 80% 的单拍时长
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

# 拍弦低音 MIDI（模拟手掌拍击琴弦的闷响）
SLAP_STRINGS = [28, 33, 40, 45]  # E1, A1, E2, A2
# AGML 有 ~50ms 的 Global Sample Start Time（拨弦起音延迟）
# 拍弦音时长必须 > 50ms 才能触发出声
SLAP_DURATION = 0.15

# KeySwitch 映射（根据 Ample Guitar 官方手册 4.2 节）
# C0(12)=Sustain, C#0(13)=Natural Harmonic, D0(14)=Palm Mute,
# D#0(15)=Slide In/Out, E0(16)=Legato Slide, F0(17)=Hammer-On/Pull-Off,
# F#0(18)=Slide Guitar
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
    """处理琶音音符（v3）：不做时间压缩，保持原节拍位置。"""
    processed = []
    for note in notes:
        note = dict(note)
        note["_adjusted_start"] = parse_beat_pos(note["beat_pos"], tempo)
        processed.append(note)
    return processed


def group_notes_by_time(notes):
    """将音符按开始时间分组，同时发生的音符在一起"""
    time_groups = defaultdict(list)
    for note in notes:
        t = round(note["_adjusted_start"], 3)  # 精确到毫秒
        time_groups[t].append(note)
    return time_groups


def main():
    parser = argparse.ArgumentParser(description="Ample Sound 吉他渲染 v7")
    parser.add_argument("song", help="歌曲名")
    parser.add_argument("track_id", help="轨道ID，如 08_节奏吉他")
    parser.add_argument("--wav-only", action="store_true", help="只生成 WAV")
    parser.add_argument("--json-only", action="store_true", help="只生成 JSON")
    args = parser.parse_args()
    
    song = args.song
    track_id = args.track_id
    track_id_clean = track_id.replace(".json", "")
    
    print("=" * 60)
    print(f"Ample Sound 渲染 v7 - {song} / {track_id_clean}")
    print("=" * 60)
    
    # 1. 查找输入文件
    print("\n[1] 查找输入 JSON...")
    input_path = find_input_json(song, track_id)
    if not input_path:
        print(f"    ❌ 未找到: {track_id_clean}*.json")
        sys.exit(1)
    print(f"    ✅ 找到: {input_path.name}")
    
    # 2. 读取数据
    print("\n[2] 读取数据...")
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    notes = data.get("notes", [])
    tempo = data.get("tempo", 68)
    beat_duration = 60.0 / tempo  # 动态计算一拍的时长
    print(f"    音符数量: {len(notes)}")
    print(f"    速度: {tempo} BPM (一拍={beat_duration:.3f}s)")
    
    # 技术统计
    techniques = {}
    for note in notes:
        t = note.get("technique", "勾弦")
        techniques[t] = techniques.get(t, 0) + 1
    print(f"    技术分布:")
    for t, count in sorted(techniques.items(), key=lambda x: -x[1]):
        print(f"      - {t}: {count}")
    
    # 3. 处理音符（计算节拍位置）
    print("\n[3] 计算节拍位置...")
    notes = process_notes_for_arp(notes, tempo)
    print(f"    处理后音符数量: {len(notes)}")
    
    # 4. 按时间分组
    print("\n[4] 按时间分组...")
    time_groups = group_notes_by_time(notes)
    print(f"    时间点数量: {len(time_groups)}")
    
    # 5. 创建输出目录
    output_dir = PROJECT_DIR / "workspace" / "project" / song / "song_engineer" / "track" / "ample_sound"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not args.json_only:
        print("\n[5] 创建渲染引擎...")
        engine = daw.RenderEngine(SAMPLE_RATE, BUFFER_SIZE)
        
        print(f"[6] 加载 VST3...")
        try:
            guitar = engine.make_plugin_processor("AmpleGuitar", VST_PATH)
            print("    ✅ VST3 加载成功!")
        except Exception as e:
            print(f"    ❌ VST3 加载失败: {e}")
            sys.exit(1)

        # ═══ 修复 dawdreamer VST3 冷启动 Bug ═══
        # 两步渲染法：先加少量音符预热，再加全部音符渲染
        print("    (VST3 预热: 第一步渲染...)")
        sorted_times = sorted(time_groups.keys())
        warmup_times = sorted_times[:5]
        warmup_end = warmup_times[-1] + 1.0 if warmup_times else 1.0
        for t in warmup_times:
            for note in time_groups[t]:
                guitar.add_midi_note(note.get("midi", 60), note.get("velocity", 80), t, 0.5)
        engine.load_graph([(guitar, [])])
        engine.render(warmup_end)
        print(f"      预热完成 (时长 {warmup_end:.1f}s)")

        # 第二步：加全部真实音符（带偏移，避开预热时间范围）
        WARMUP_OFFSET = 5.5
        print(f"    (VST3 已预热，添加全部 {len(sorted_times)} 个时间点的音符，偏移 {WARMUP_OFFSET}s...)")
        
        for t in sorted_times:
            group = time_groups[t]
            is_slap = any(n.get("technique") == "拍弦" for n in group)

            if is_slap:
                # 触发拍弦打击音效（不 continue，同节拍的"四勾"正常发声）
                slap_vel = random.randint(110, 127)
                slap_midi = random.choice(SLAP_STRINGS)
                guitar.add_midi_note(slap_midi, slap_vel, t + WARMUP_OFFSET - 0.01, SLAP_DURATION)
                print(f"      拍弦 t={t+WARMUP_OFFSET:.3f}s, midi={slap_midi}, vel={slap_vel}")

            # 按音高排序
            group_sorted = sorted(group, key=lambda x: x.get("midi", 60))
            note_count = len(group_sorted)

            for idx, note in enumerate(group_sorted):
                technique = note.get("technique", "勾弦")
                
                # 跳过标记为"拍弦"的占位音符（上方已触发打击音效）
                if technique == "拍弦":
                    continue

                midi = note.get("midi", 60)
                velocity = note.get("velocity", 80)
                duration = parse_duration(note.get("duration", "4分"), tempo)
                human_vel = min(127, max(1, int(velocity * VELOCITY_BOOST) + random.randint(-5, 5)))

                # ✅ 技法时长与延迟微调
                if technique == "琶音":
                    # 琶音：动态均分，让和弦饱满地铺满 80% 的一拍时间
                    arp_delay = (beat_duration * 0.8) / max(1, note_count - 1)
                    delay = idx * arp_delay
                    final_duration = duration * 1.6
                elif "勾" in technique:  # 匹配"5勾弦"和"四勾"
                    # 勾弦：多指同时发力，延迟极短，仅保留 ±3ms 人感误差
                    delay = random.uniform(-0.003, 0.003)
                    final_duration = duration * 1.3
                else:
                    # 常规扫弦
                    delay = idx * STRUM_DELAY
                    final_duration = duration * 1.3

                human_start = t + WARMUP_OFFSET + delay
                
                # KeySwitch 处理
                tech_key = TECH_TO_KEYSWITCH.get(technique, None)
                if tech_key:
                    ks_note = KEYSWITCH[tech_key]
                    guitar.add_midi_note(ks_note, 127, human_start - 0.005, 0.01)

                guitar.add_midi_note(midi, human_vel, human_start, final_duration)
        
        # 计算总时长
        max_time = max(sorted_times) + WARMUP_OFFSET if sorted_times else 0
        for note in notes:
            dur = parse_duration(note.get("duration", "4分"), tempo)
            max_time = max(max_time, note["_adjusted_start"] + WARMUP_OFFSET + dur * 1.5)
        
        print(f"\n[8] 渲染音频 ({max_time + 2:.1f} 秒)...")
        graph = [(guitar, [])]
        engine.load_graph(graph)
        engine.render(max_time + 2.0)
        
        print("\n[9] 保存音频...")
        audio_data = engine.get_audio()
        output_wav = output_dir / f"{track_id_clean}.wav"
        import tempfile
        import shutil
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        sf.write(tmp_path, audio_data.T, SAMPLE_RATE)
        if output_wav.exists():
            try:
                output_wav.unlink()
            except PermissionError:
                pass
        shutil.copy2(tmp_path, str(output_wav))
        Path(tmp_path).unlink()
        print(f"    ✅ 音频已保存: {output_wav}")
        print(f"    大小: {os.path.getsize(output_wav) / 1024 / 1024:.2f} MB")
    
    # 10. 生成元数据 JSON
    if not args.wav_only:
        print("\n[10] 生成元数据 JSON...")
        output_json = output_dir / f"{track_id_clean}.json"
        
        output_data = {
            "schema": "track.ample_sound.v1",
            "track_id": data.get("track_id", 8),
            "name": data.get("name", track_id_clean),
            "instrument": "Ample Guitar M Lite",
            "vst3": VST_PATH,
            "tempo": tempo,
            "sample_rate": SAMPLE_RATE,
            "notes_count": len(notes),
            "duration_seconds": max_time + 2.0 if not args.json_only else None,
            "techniques": techniques,
            "source": input_path.name,
            "renderer": "dawdreamer_v7",
            "improvements": [
                "修复拍弦吞音：移除全局 continue，实现拍弦与四勾的完美同时发声",
                "修复勾弦生硬：识别'5勾弦'和'四勾'，消除逐弦延迟（仅保留 ±3ms 人感误差）",
                "修复琶音急促：根据当前 BPM 动态分配逐弦间距，让音符铺满 80% 的单拍时长"
            ]
        }
        
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"    ✅ JSON 已保存: {output_json}")
    
    print("\n" + "=" * 60)
    print("🎸 Ample Sound 渲染完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()