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


def _load_env():
    """从项目根 .env 读取配置（轻量解析，不引入 dotenv 依赖）"""
    env = {}
    env_path = PROJECT_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()
    return env


_ENV = _load_env()

# VST3 路径（从 .env 的 AGML_PATH 读取，回退到默认值）
VST_PATH = _ENV.get("AGML_PATH", "C:/Program Files/Common Files/VST3/AGML.vst3")

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
        "全全": beat_duration * 8,
        "全": beat_duration * 4,
        "2分": beat_duration * 2,
        "4分": beat_duration,
        "8分": beat_duration / 2,
        "16分": beat_duration / 4,
        "32分": beat_duration / 8,
    }
    return mapping.get(duration_str, beat_duration)


def find_input_json(song, track_id):
    """查找输入 JSON 文件。track_id 可能带子路径前缀(如 ample_sound/08_节奏吉他)。
    优先按完整路径匹配，避免误命中 track/ 下同名旧文件。"""
    track_dir = PROJECT_DIR / "workspace" / "project" / song / "song_engineer" / "track"
    clean = track_id.replace("\\", "/").strip("/")
    if clean.endswith(".json"):
        clean = clean[:-5]
    # 1. 优先：完整相对路径（如 track/ample_sound/08_节奏吉他.json）
    full = track_dir / (clean + ".json")
    if full.exists():
        return full
    # 2. 完整路径前缀模糊（如 ample_sound/08_节奏吉他.data.test）
    for sub in track_dir.rglob(clean.split("/")[-1] + "*.json"):
        # 只接受路径以 clean 为后缀的（含子目录前缀的优先）
        rel = str(sub.relative_to(track_dir)).replace("\\", "/")
        if rel.startswith(clean) or rel == clean.split("/")[-1] + ".json":
            # 但要排除 track/{name}.json 旧文件当 clean 带前缀时
            if "/" in clean and rel == clean.split("/")[-1] + ".json":
                continue
            return sub
    # 3. 仅文件名匹配（clean 不带前缀时）
    name = clean.split("/")[-1]
    exact = track_dir / f"{name}.json"
    if exact.exists():
        return exact
    for sub in track_dir.rglob(f"{name}.json"):
        return sub
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


def expand_note(note):
    """把一个 note 展开成 [(midi, velocity), ...] 单音列表。
    midi/actual/velocity 字段可能是单值或数组（柱式和弦/琶音多音）。"""
    midi_field = note.get("midi", 60)
    vel_field = note.get("velocity", 80)
    if isinstance(midi_field, list):
        midis = midi_field
    else:
        midis = [midi_field]
    if isinstance(vel_field, list):
        vels = vel_field
    else:
        vels = [vel_field] * len(midis)
    # 长度对齐
    while len(vels) < len(midis):
        vels.append(vels[-1] if vels else 80)
    return [(int(m), int(v)) for m, v in zip(midis, vels)]


def main():
    global n
    parser = argparse.ArgumentParser(description="Ample Sound 吉他渲染 v7.1")
    parser.add_argument("song", help="歌曲名")
    parser.add_argument("track_id", help="轨道ID，如 08_节奏吉他")
    parser.add_argument("--wav-only", action="store_true", help="只生成 WAV")
    parser.add_argument("--json-only", action="store_true", help="只生成 JSON")
    args = parser.parse_args()
    
    song = args.song
    track_id = args.track_id
    # track_id 可能带路径前缀(如 ample_sound/08_节奏吉他)，只取文件名部分做输出名
    track_id_clean = track_id.replace("\\", "/").split("/")[-1].replace(".json", "")
    
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
                    for m, v in expand_note(note):
                        guitar.add_midi_note(m, v, wt, 0.5)

        # 真实音符：从 WARMUP_OFFSET 开始
        index = 1
        for t in sorted_times:
            print(f"### 同一个时间的音素 {index}### ")
            index = index + 1
            group = time_groups[t]
            is_slap = any(n.get("technique") == "拍弦" for n in group)


            if is_slap:
                # 拍弦：1) FX音效(90) 短促打击 2) 弦的余音(用note自己的midi+duration)
                slap_notes = [n for n in group if n.get("technique") == "拍弦"]
                fx_midi = 90  # 89弦摩擦/换和弦, 90拍弦音
                fx_dur = 0.5
                slap_pre_time = - 0.01
                slap_string_pre_time = 0.00
                for sn in slap_notes:
                    base_t = t + WARMUP_OFFSET
                    fx_vel = min(127, max(1, int(sn.get("velocity", 50) * 2.5)))
                    # FX 打击音效
                    guitar.add_midi_note(fx_midi, fx_vel, base_t - slap_pre_time, fx_dur)
                    # 弦余音：用 note 自己的 midi(支持数组) 和 duration
                    ring_dur = parse_duration(sn.get("duration", "4分"), tempo) * 1.3
                    ring_vel = min(127, max(1, int(sn.get("velocity", 50) * 0.5)))  # 余音力度低些
                    for m, _ in expand_note(sn):
                        guitar.add_midi_note(m, ring_vel, base_t -slap_string_pre_time, ring_dur)
                    print(f"      拍弦 t={base_t:.3f}s FX(midi={fx_midi},vel={fx_vel},dur={fx_dur}) + 余音(midi={sn.get('midi')},vel={ring_vel},dur={ring_dur:.3f})")

            # 按音高展开成单音列表并排序（拍弦占位符已过滤）
            flat_notes = []  # [(midi, velocity, technique, beat_pos, duration_str)]
            for n in group:
                if n.get("technique") == "拍弦":
                    continue
                tech = n.get("technique", "勾弦")
                for m, v in expand_note(n):
                    flat_notes.append((m, v, tech, n.get("beat_pos", "N/A"),n.get("sepa_factor",1.0), n.get("duration", "4分")))
            flat_notes.sort(key=lambda x: x[0])  # 按音高升序
            note_count = len(flat_notes)

            for valid_idx, (midi, velocity, technique, beat_pos, sepa_factor,dur_str) in enumerate(flat_notes):
                duration = parse_duration(dur_str, tempo)

                human_vel = min(127, max(1, int(velocity * VELOCITY_BOOST) + random.randint(-5, 5)))

                # 如果当前拍有拍弦，将正常的弦音音效压制，凸显拍弦感
                if is_slap:
                    human_vel = max(1, int(human_vel * 0.3))

                # 技法时长与延迟微调
                if technique == "琶音":
                    # sepa_factor: 琶音分离系数（默认1）。>1 更分散(慢琶音), <1 更紧凑(快琶音), 0=柱式齐奏
                    # arp_total_time = 琶音首尾音的间隔时间(秒)
                    base_arp_time = min(0.3, beat_duration * 0.4)
                    arp_total_time = base_arp_time * sepa_factor
                    # 每相邻两音的间隔
                    arp_delay = arp_total_time / max(1, note_count - 1) if note_count > 1 else 0.0
                    delay = valid_idx * arp_delay
                    final_duration = duration * 1.6
                    print(f"  valid_idx={valid_idx},sepa_factor={sepa_factor}, arp_total_time={arp_total_time:.3f}, arp_delay={arp_delay:.3f}, delay={delay:.3f}, final_duration={final_duration:.3f}")
                elif "勾" in technique:
                    # 勾弦(5勾弦/四勾): 多指依次拨弦, 用 sepa_factor 控制分离度
                    # 基准比琶音短(勾弦是快速依次拨), sepa_factor=1 时约0.12s跨度
                    base_pick_time = min(0.12, beat_duration * 0.15)
                    pick_total_time = base_pick_time * sepa_factor
                    pick_delay = pick_total_time / max(1, note_count - 1) if note_count > 1 else 0.0
                    delay = valid_idx * pick_delay + random.uniform(-0.002, 0.002)  # 顺序拨 + 微抖动
                    final_duration = duration * 1.3
                    print(f"  valid_idx={valid_idx},sepa_factor={sepa_factor}, pick_total_time={pick_total_time:.3f}, delay={delay:.4f}, final_duration={final_duration:.3f}")
                else:
                    delay = valid_idx * STRUM_DELAY
                    final_duration = duration * 1.3

                human_start = t + WARMUP_OFFSET + delay

                tech_key = TECH_TO_KEYSWITCH.get(technique, None)
                if tech_key:
                    ks_note = KEYSWITCH[tech_key]
                    guitar.add_midi_note(ks_note, 127, human_start - 0.005, 0.01)
                    print(f"     弹奏 tech:{technique} t={human_start - 0.005:.3f}s, ks_midi={ks_note}, human_vel={127}")
                guitar.add_midi_note(midi, human_vel, human_start, final_duration)
                print(f"     弹奏{technique} beat_pos={beat_pos}, t={human_start:.3f}s, midi={midi}, human_vel={human_vel}, final_duration={final_duration:.3f}, delay={delay:.4f}")
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
