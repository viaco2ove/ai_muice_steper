"""
Ample Sound 贝斯音轨渲染脚本 v1.0
使用 dawdreamer + Ample Bass P Lite (ABPL) VST3
- 单音低音线, 长音 sustain 为主
- 支持 "贝斯长音"(finger sustain) / "闷音"(palm mute) / "击勾弦"(legato) 技法
- VST3 路径从 .env 的 ABPL_PATH 读取
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import argparse
import json
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

# VST3 路径(从 .env 的 ABPL_PATH 读取, 回退默认)
VST_PATH = _ENV.get("ABPL_PATH", "C:/Program Files/Common Files/VST3/ABPL.vst3")

# 贝斯参数
VELOCITY_BOOST = 1.05  # 贝斯力度增强(比吉他小, 低音易过载)

# ABPL KeySwitch 映射 (Ample Bass P Lite, 与 AGML 类似布局)
# 参考 AGML: 12=C0 sustain, 14=D0 palm mute, 17=F0 hammer/pull, 16=E0 legato slide
KEYSWITCH = {
    "sustain": 12,        # C0 - 指弹长音(Sustain / Finger)
    "palm_mute": 14,      # D0 - 闷音(Palm Mute)
    "hammer_pull": 17,    # F0 - 击勾弦(Hammer-On & Pull-Off)
    "legato_slide": 16,   # E0 - 连奏滑音
    "slide": 15,          # D#0 - 滑音
    "harmonics": 13,      # C#0 - 泛音
}

# 中文技法 -> keyswitch 名
TECH_TO_KEYSWITCH = {
    "贝斯长音": "sustain",
    "长音": "sustain",
    "闷音": "palm_mute",
    "击勾弦": "hammer_pull",
    "连奏滑音": "legato_slide",
    "滑音": "slide",
    "泛音": "harmonics",
}


def parse_beat_pos(beat_pos, tempo=68):
    """解析 beat_pos 格式 '小节.拍.十六分', 返回秒"""
    parts = str(beat_pos).split(".")
    if len(parts) < 2:
        return 0.0
    bar = int(parts[0])
    beat = int(parts[1])
    sub = int(parts[2]) if len(parts) > 2 else 1
    beat_duration = 60.0 / tempo
    bar_duration = beat_duration * 4
    sub_duration = beat_duration / 4
    return (bar - 1) * bar_duration + (beat - 1) * beat_duration + (sub - 1) * sub_duration


def parse_duration(duration_str, tempo=68):
    """中文时值 -> 秒"""
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
    """查找输入 JSON. track_id 可能带子路径前缀."""
    track_dir = PROJECT_DIR / "workspace" / "project" / song / "song_engineer" / "track"
    clean = track_id.replace("\\", "/").strip("/")
    if clean.endswith(".json"):
        clean = clean[:-5]
    # 1. 完整相对路径
    full = track_dir / (clean + ".json")
    if full.exists():
        return full
    # 2. 各子目录同名
    name = clean.split("/")[-1]
    for sub in track_dir.rglob(f"{name}.json"):
        return sub
    # 3. 前缀模糊
    for sub in track_dir.rglob(f"{name}*.json"):
        return sub
    return None


def expand_note(note):
    """把 note 展开成 [(midi, velocity)] 单音列表(支持数组 midi)."""
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
    while len(vels) < len(midis):
        vels.append(vels[-1] if vels else 80)
    return [(int(m), int(v)) for m, v in zip(midis, vels)]


def main():
    parser = argparse.ArgumentParser(description="Ample Sound 贝斯渲染 v1.0")
    parser.add_argument("song", help="歌曲名")
    parser.add_argument("track_id", help="轨道ID, 如 13_轻贝斯")
    parser.add_argument("--wav-only", action="store_true", help="只生成 WAV")
    parser.add_argument("--json-only", action="store_true", help="只生成 JSON")
    args = parser.parse_args()

    song = args.song
    track_id = args.track_id
    track_id_clean = track_id.replace("\\", "/").split("/")[-1].replace(".json", "")

    print("=" * 60)
    print(f"Ample Sound 贝斯渲染 - {song} / {track_id_clean}")
    print("=" * 60)

    # 1. 查找输入
    input_path = find_input_json(song, track_id)
    if not input_path:
        print("    ❌ 未找到输入文件")
        sys.exit(1)

    # 2. 读数据
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    notes = data.get("notes", [])
    tempo = data.get("tempo", 68)
    beat_duration = 60.0 / tempo

    # 计算节拍位置 + 按时间分组
    for n in notes:
        n["_adjusted_start"] = parse_beat_pos(n.get("beat_pos", "1.1"), tempo)
    time_groups = defaultdict(list)
    for n in notes:
        time_groups[round(n["_adjusted_start"], 3)].append(n)
    sorted_times = sorted(time_groups.keys())
    time_idx = {t: i for i, t in enumerate(sorted_times)}

    # 3. 输出目录
    output_dir = PROJECT_DIR / "workspace" / "project" / song / "song_engineer" / "track" / "ample_sound"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not args.json_only:
        engine = daw.RenderEngine(SAMPLE_RATE, BUFFER_SIZE)
        try:
            bass = engine.make_plugin_processor("AmpleBass", VST_PATH)
        except Exception as e:
            print(f"    ❌ VST3 加载失败: {e}")
            sys.exit(1)

        # 单次渲染: 预热段 + 真实段一起, 渲染后裁掉预热段
        WARMUP_OFFSET = 5.5

        # 预热音符(前几个, 铺在 0~WARMUP_OFFSET)
        warmup_times = sorted_times[:5]
        if warmup_times:
            warmup_span = max(0.1, WARMUP_OFFSET - 0.5)
            step = warmup_span / max(1, len(warmup_times))
            for i, t in enumerate(warmup_times):
                wt = i * step
                for note in time_groups[t]:
                    for m, v in expand_note(note):
                        bass.add_midi_note(m, v, wt, 0.5)

        # 真实音符
        idx = 1
        for t in sorted_times:
            print(f"### 贝斯音 {idx} ###")
            idx += 1
            group = time_groups[t]
            # 展开成单音并排序
            flat = []
            for n in group:
                tech = n.get("technique", "贝斯长音")
                for m, v in expand_note(n):
                    flat.append((m, v, tech, n.get("beat_pos", "N/A"), n.get("duration", "4分")))
            flat.sort(key=lambda x: x[0])

            for valid_idx, (midi, velocity, technique, beat_pos, dur_str) in enumerate(flat):
                duration = parse_duration(dur_str, tempo)
                human_vel = min(127, max(1, int(velocity * VELOCITY_BOOST) + random.randint(-3, 3)))
                base_t = t + WARMUP_OFFSET

                # ── 贝斯技法处理 ──
                # 击勾弦: legato, 时值延续到下一音, 力度降低
                if technique == "击勾弦":
                    final_duration = duration * 1.05
                    ti = time_idx.get(t)
                    if ti is not None and ti + 1 < len(sorted_times):
                        gap = sorted_times[ti + 1] - t
                        if gap <= beat_duration * 2:
                            final_duration = max(0.05, gap * 1.02)
                    human_vel = max(1, int(human_vel * 0.7))
                    ks = KEYSWITCH["hammer_pull"]
                    bass.add_midi_note(ks, 127, base_t - 0.005, 0.01)
                    bass.add_midi_note(midi, human_vel, base_t, final_duration)
                    print(f"     击勾弦(legato) {beat_pos} t={base_t:.3f}s midi={midi} vel={human_vel} dur={final_duration:.3f}")
                    continue

# 滑音(slide): 单击滑奏, 不延续到下一音
                if technique == "滑音":
                    final_duration = duration * 1.1  # 滑音略带拖尾
                    ks = KEYSWITCH["slide"]
                    bass.add_midi_note(ks, 127, base_t - 0.005, 0.01)
                    bass.add_midi_note(midi, human_vel, base_t, final_duration)
                    print(f"     滑音(slide) {beat_pos} t={base_t:.3f}s midi={midi} vel={human_vel} dur={final_duration:.3f}")
                    continue

                # 连奏滑音
                if technique == "连奏滑音":
                    final_duration = duration * 1.2
                    ti = time_idx.get(t)
                    if ti is not None and ti + 1 < len(sorted_times):
                        gap = sorted_times[ti + 1] - t
                        if gap <= beat_duration * 2:
                            final_duration = max(0.05, gap * 1.05)
                    ks = KEYSWITCH["legato_slide"]
                    bass.add_midi_note(ks, 127, base_t - 0.005, 0.01)
                    bass.add_midi_note(midi, human_vel, base_t, final_duration)
                    print(f"     连奏滑音(slide) {beat_pos} t={base_t:.3f}s midi={midi} vel={human_vel} dur={final_duration:.3f}")
                    continue

                # 闷音: 短促
                if technique == "闷音":
                    final_duration = duration * 0.8
                    ks = KEYSWITCH["palm_mute"]
                    bass.add_midi_note(ks, 127, base_t - 0.005, 0.01)
                    bass.add_midi_note(midi, human_vel, base_t, final_duration)
                    print(f"     闷音(palm mute) {beat_pos} t={base_t:.3f}s midi={midi} vel={human_vel} dur={final_duration:.3f}")
                    continue

                # 默认: 贝斯长音(sustain / finger)
                # 贝斯长音时值略延长, 低音余音自然衰减
                final_duration = duration * 1.3
                # sustain 默认 keyswitch(ABPL 是默认指弹音色, 不显式发也可)
                bass.add_midi_note(midi, human_vel, base_t, final_duration)
                print(f"     {technique} {beat_pos} t={base_t:.3f}s midi={midi} vel={human_vel} dur={final_duration:.3f}")

        # 总时长 + 渲染
        max_time = WARMUP_OFFSET
        if sorted_times:
            max_time = max(max_time, max(sorted_times) + WARMUP_OFFSET)
        for n in notes:
            dur = parse_duration(n.get("duration", "4分"), tempo)
            max_time = max(max_time, n["_adjusted_start"] + WARMUP_OFFSET + dur * 1.5)

        engine.load_graph([(bass, [])])
        engine.render(max_time + 2.0)

        # 裁掉预热段
        audio_data = np.array(engine.get_audio(), copy=True)
        warmup_samples = int(WARMUP_OFFSET * SAMPLE_RATE)
        if audio_data.ndim == 2:
            trimmed = audio_data[:, warmup_samples:]
        else:
            trimmed = audio_data[warmup_samples:]

        # 末尾淡出
        tail = min(int(0.05 * SAMPLE_RATE), trimmed.shape[-1] // 4)
        if tail > 0:
            fade = np.linspace(1.0, 0.0, tail)
            if trimmed.ndim == 2:
                trimmed[:, -tail:] *= fade
            else:
                trimmed[-tail:] *= fade
        # 开头淡入
        head = min(int(0.01 * SAMPLE_RATE), trimmed.shape[-1] // 4)
        if head > 0:
            fade_in = np.linspace(0.0, 1.0, head)
            if trimmed.ndim == 2:
                trimmed[:, :head] *= fade_in
            else:
                trimmed[:head] *= fade_in

        # 保存
        output_wav = output_dir / f"{track_id_clean}.wav"
        import tempfile, shutil
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        sf.write(tmp_path, trimmed.T if trimmed.ndim == 2 else trimmed, SAMPLE_RATE)
        if output_wav.exists():
            try: output_wav.unlink()
            except PermissionError: pass
        shutil.copy2(tmp_path, str(output_wav))
        Path(tmp_path).unlink()
        print(f"    ✅ 贝斯音频已保存(已裁预热段): {output_wav}")

    # 元数据 JSON
    if not args.wav_only:
        output_json = output_dir / f"{track_id_clean}.json"
        output_data = {
            "schema": "track.ample_sound_bass.v1",
            "track_id": data.get("track_id", 13),
            "name": data.get("name", track_id_clean),
            "tempo": tempo,
            "source": input_path.name,
            "renderer": "dawdreamer_abpl_v1.0",
            "vst": "ABPL"
        }
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"    ✅ JSON 已保存: {output_json}")


if __name__ == "__main__":
    main()