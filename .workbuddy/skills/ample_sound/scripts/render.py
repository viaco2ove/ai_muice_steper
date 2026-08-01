"""
Ample Sound 吉他音轨渲染脚本 v4
使用 dawdreamer + Ample Guitar M Lite VST3

修复点（相比 v3）：
1. 拍弦改为 F#5 (MIDI 78) 正确的 FX 音效（之前错用 C6 / 上扫噪声2）
2. KeySwitch 映射修正：闷音 D0(14) / 泛音 C#0(13) / 连奏滑音 E0(16) / 击勾弦 F0(17)
3. 拍弦是打击音效叠加在弦音上，不再跳过其他音符
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
STRUM_DELAY = 0.018       # 逐弦时差（秒），多指勾弦时相邻弦间隔 18ms
ARP_STRUM_DELAY = 0.030   # 琶音逐弦时差，稍大一些 30ms
VELOCITY_BOOST = 1.10     # 力度增强系数

# 拍弦 FX 音符（MIDI 78 = F#5，AGML 效果音组：F#5 = 拍弦）
SLAP_FX_MIDI = 78

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
    "tap": 19,             # G0 - 保留，未在手册中找到对应
}

TECH_TO_KEYSWITCH = {
    "闷音": "palm_mute",
    "泛音": "harmonics",
    "点弦": "tap",
    "滑音": "slide",
    "连奏滑音": "legato_slide",
    "击勾弦": "hammer_pull",
    # 拍弦不在这里，走 SLAP_FX_MIDI 路线
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
    """
    处理琶音音符（v3）：不做时间压缩，保持原节拍位置。
    每个琶音音符后续由渲染循环按音高排序后加逐弦时差。
    """
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
    parser = argparse.ArgumentParser(description="Ample Sound 吉他渲染 v4")
    parser.add_argument("song", help="歌曲名")
    parser.add_argument("track_id", help="轨道ID，如 08_节奏吉他")
    parser.add_argument("--wav-only", action="store_true", help="只生成 WAV")
    parser.add_argument("--json-only", action="store_true", help="只生成 JSON")
    args = parser.parse_args()
    
    song = args.song
    track_id = args.track_id
    track_id_clean = track_id.replace(".json", "")
    
    print("=" * 60)
    print(f"Ample Sound 渲染 v4 - {song} / {track_id_clean}")
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
    print(f"    音符数量: {len(notes)}")
    print(f"    速度: {tempo} BPM")
    
    # 技术统计
    techniques = {}
    for note in notes:
        t = note.get("technique", "勾弦")
        techniques[t] = techniques.get(t, 0) + 1
    print(f"    技术分布:")
    for t, count in sorted(techniques.items(), key=lambda x: -x[1]):
        print(f"      - {t}: {count}")
    
    # 3. 处理琶音（压缩时间）
    print("\n[3] 处理琶音音符（保持节拍，渲染时加逐弦时差）...")
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
        
        print(f"[7] 添加 MIDI 音符 (v4: 正确 KeySwitch + 拍弦 F#5)...")
        
        # 按时间排序
        sorted_times = sorted(time_groups.keys())
        
        for t in sorted_times:
            group = time_groups[t]

            # === 1. 拍弦：发送 AGML 的 F#5 (MIDI 78) 拍弦 FX 音效 ===
            # 拍弦是打击音效，叠加在普通弦音上，不跳过其他音符
            is_slap = any(n.get("technique") == "拍弦" for n in group)
            if is_slap:
                slap_vel = random.randint(100, 120)
                guitar.add_midi_note(SLAP_FX_MIDI, slap_vel, t, 0.15)
                # 不 continue，继续发送下面的弦音

            # === 2. 非拍弦（或拍弦叠加的弦音）：按音高排序加逐弦时差 ===
            group_sorted = sorted(group, key=lambda x: x.get("midi", 60))

            for idx, note in enumerate(group_sorted):
                midi = note.get("midi", 60)
                velocity = note.get("velocity", 80)
                technique = note.get("technique", "勾弦")
                duration_str = note.get("duration", "4分")
                duration = parse_duration(duration_str, tempo)

                # 力度：boost + 小幅随机起伏（±5），有人感
                human_vel = min(127, max(1, int(velocity * VELOCITY_BOOST) + random.randint(-5, 5)))

                # 时长调整
                if technique == "琶音":
                    dur_mult = 1.6   # 琶音保持延音
                    strum_delay = ARP_STRUM_DELAY
                else:
                    dur_mult = 1.3   # 勾弦充分振动
                    strum_delay = STRUM_DELAY

                # 逐弦时差：低音弦先响，高音弦依次间隔
                delay = idx * strum_delay
                # 人感抖动：±2ms
                human_start = t + delay + random.uniform(-0.002, 0.002)
                final_duration = duration * dur_mult

                # KeySwitch 处理（闷音/泛音/点弦）
                tech_key = TECH_TO_KEYSWITCH.get(technique, None)
                if tech_key:
                    ks_note = KEYSWITCH[tech_key]
                    guitar.add_midi_note(ks_note, 127, human_start - 0.005, 0.01)

                # 发送吉他音符，严格基于原节拍 t + 逐弦时差
                guitar.add_midi_note(midi, human_vel, human_start, final_duration)
        
        # 计算总时长
        max_time = max(sorted_times) if sorted_times else 0
        for note in notes:
            dur = parse_duration(note.get("duration", "4分"), tempo)
            max_time = max(max_time, note["_adjusted_start"] + dur * 1.5)
        
        print(f"\n[8] 渲染音频 ({max_time + 2:.1f} 秒)...")
        graph = [(guitar, [])]
        engine.load_graph(graph)
        engine.render(max_time + 2.0)
        
        print("\n[9] 保存音频...")
        audio_data = engine.get_audio()
        output_wav = output_dir / f"{track_id_clean}.wav"
        # Windows 上 soundfile 对中文路径有问题，先写到 temp 再 copy 过去
        import tempfile
        import shutil
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        sf.write(tmp_path, audio_data.T, SAMPLE_RATE)
        # 先删旧文件（如果存在且被占用），再用 copy（跨盘符不支持 rename）
        if output_wav.exists():
            try:
                output_wav.unlink()
            except PermissionError:
                pass  # 文件被占用，跳过删除让 copy 覆盖
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
            "renderer": "dawdreamer_v4",
            "improvements": [
                "删除 NOTE_OVERLAP，恢复正确节拍",
                "拍弦改为 F#5 (MIDI 78) 真实拍弦 FX 音效（之前错用 C6 上扫噪声）",
                "KeySwitch 映射修正：闷音 D0 / 泛音 C#0 / 连奏滑音 E0 / 击勾弦 F0",
                "拍弦是打击音效，叠加在弦音上（不再跳过其他音符）",
                "逐弦时差 18ms（勾弦）/ 30ms（琶音）",
                "力度+10% 加随机起伏（人感）",
                "琶音保留自然延音，不压缩时长"
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