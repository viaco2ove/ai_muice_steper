# -*- coding: utf-8 -*-
"""
remix.py - remix-master 技能核心脚本：配置驱动的音轨混音器

读 remix.json，按每条轨配置（vol/gain_db/mute/pan/source）混合成最终母带 wav。

核心解决「放大主唱没有效果」问题：
  主唱轨优先用 02_主唱.wav 真实 OpenUTAU 干声（不是 FluidSynth 合成人声），
  所以改 remix.json 里 02_主唱 的 gain_db / vol 后重混，立刻见效。

source 取值：
  auto（默认）：优先 <track>.wav 真实干声，找不到 fallback <track>.mid 走 FluidSynth 合成
  wav：强制用 wav 干声（必须存在，否则跳过该轨并告警）
  midi：强制 <track>.mid 走 FluidSynth 合成（program/soundfont 从 <track>.json 读）

音量参数优先级：vol（线性倍率）× 10^(gain_db/20)（分贝）。mute=true 直接跳过。

用法：
  # 1. 自动生成默认 remix.json（扫描 track 目录下所有 wav）
  ./.venv/python.exe .workbuddy/skills/remix-master/scripts/remix.py --project 走在 --init

  # 2. 编辑 remix.json（如把 02_主唱 的 gain_db 改成 3.0）

  # 3. 重混
  ./.venv/python.exe .workbuddy/skills/remix-master/scripts/remix.py --project 走在
  # -> full_remix.wav
"""
import os
import sys
import json
import math
import shutil
import tempfile
import argparse
import numpy as np
import soundfile as sf

# ---------- .env 读取（FluidSynth fallback 用） ----------
_env = {}
_cur = os.path.dirname(os.path.abspath(__file__))
for _ in range(6):
    _c = os.path.join(_cur, ".env")
    if os.path.exists(_c):
        with open(_c, encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    _env[k] = v
        break
    _cur = os.path.dirname(_cur)
FS_PATH = _env.get("fluidsynth_path", "")
SF_DIR = _env.get("soundfonts_path", "")
if FS_PATH:
    os.environ["PATH"] = os.path.join(FS_PATH, "bin") + ";" + os.environ.get("PATH", "")

SAMPLE_RATE = 44100


# ==================== 音频读写 ====================
def load_wav_mono(path, target_sr=SAMPLE_RATE):
    """读 wav，转 mono float32，重采样到 target_sr。返回 (audio, sr)。"""
    data, sr = sf.read(path, dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)
    if sr != target_sr:
        from scipy.interpolate import interp1d
        x_old = np.linspace(0, 1, len(data))
        x_new = np.linspace(0, 1, int(len(data) * target_sr / sr))
        data = interp1d(x_old, data, kind="linear")(x_new).astype(np.float32)
    return data, target_sr


def find_sf(preferred=None):
    """查找 SoundFont。优先 preferred，否则 GeneralUser，否则任一 sf2/sf3。"""
    if preferred:
        p = os.path.join(SF_DIR, preferred)
        if os.path.exists(p):
            return p
    if os.path.isdir(SF_DIR):
        for f in sorted(os.listdir(SF_DIR)):
            if "GeneralUser" in f and f.lower().endswith((".sf2", ".sf3")):
                return os.path.join(SF_DIR, f)
        sfs = [f for f in os.listdir(SF_DIR) if f.lower().endswith((".sf2", ".sf3"))]
        if sfs:
            return os.path.join(SF_DIR, sfs[0])
    return None


# ==================== MIDI 合成 fallback（精简，复用 synth_multitrack_fs 思路） ====================
DUR2TICKS = {"16分": 120, "8分": 240, "4分": 480, "2分": 960, "全分": 480, "全延": 480, "": 240}
DYN2VEL = {"ppp": 25, "pp": 45, "p": 60, "mp": 75, "mf": 85, "f": 95, "ff": 105, "fff": 115}


def note_name_to_midi(name):
    import re
    if not name or name.strip() in ("", "留白", "slap", "noise"):
        return None
    name = name.replace("泛音", "").strip()
    m = re.match(r"([A-G])([#b]?)(-?\d+)", name)
    if not m:
        return None
    base = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[m.group(1)]
    if m.group(2) == "#":
        base += 1
    elif m.group(2) == "b":
        base -= 1
    return base + (int(m.group(3)) + 1) * 12


def bar_offset(bar, beat, frac):
    return (bar - 1) * 4 * 480 + (beat - 1) * 480 + (frac - 1) * 240


def json_to_events(data, bpm=68):
    """从 track json 提取 (tick, midi, dur_tick, vel) 事件列表。"""
    events = []
    for i, bar in enumerate(data.get("bars", [])):
        for b in bar.get("beats", []):
            mn = note_name_to_midi(b.get("actual") or b.get("note") or "")
            if mn is None:
                continue
            pos = b.get("pos", "1.1").split(".")
            try:
                beat, frac = int(pos[0]), int(pos[1]) if len(pos) > 1 else 1
            except Exception:
                continue
            tick = bar_offset(i + 1, beat, frac)
            dur = DUR2TICKS.get(b.get("dur", "4分"), 480)
            vel = DYN2VEL.get(b.get("dynamics", "p"), 60)
            events.append((tick, mn, dur, vel))
    m = data.get("melody_note_level")
    if m:
        for notes in m.get("sections", {}).values():
            for n in notes:
                mn = n.get("midi")
                if mn is None or mn < 0:
                    continue
                bp = n.get("beat_pos", "1.1.1").split(".")
                try:
                    bar = int(bp[0]); beat = int(bp[1]) if len(bp) > 1 else 1
                    fs = bp[2] if len(bp) > 2 else "1"
                    if fs == "末":
                        beat = min(beat + 1, 4); frac = 1
                    else:
                        frac = int(fs)
                except Exception:
                    continue
                tick = bar_offset(bar, beat, frac)
                dur = DUR2TICKS.get(n.get("duration", "8分"), 240)
                vel = n.get("velocity", 60)
                if isinstance(vel, str):
                    vel = DYN2VEL.get(vel, 60)
                events.append((tick, mn, dur, int(vel)))
    for n in data.get("notes", []):
        if not isinstance(n, dict):
            continue
        nn = n.get("actual") or n.get("note") or ""
        if nn in ("slap", "noise") or n.get("midi", -1) == 0:
            continue
        mn = note_name_to_midi(nn)
        if mn is None:
            mn = n.get("midi")
            if mn is None or mn <= 0:
                continue
        bp = n.get("beat_pos", "1.1.1").split(".")
        try:
            bar = int(bp[0]); beat = int(bp[1]) if len(bp) > 1 else 1
            fs = bp[2] if len(bp) > 2 else "1"
            if fs == "末":
                beat = min(beat + 1, 4); frac = 1
            else:
                frac = int(fs)
        except Exception:
            continue
        tick = bar_offset(bar, beat, frac)
        dur = DUR2TICKS.get(n.get("duration", "4分"), 480)
        vel = n.get("velocity", 60)
        if isinstance(vel, str):
            vel = DYN2VEL.get(vel, 60)
        events.append((tick, mn, dur, int(vel)))
    return events


def render_midi_track(json_path, sf_path, program, bpm=68, gain=2.5):
    """读 track json -> 事件 -> FluidSynth 渲染 -> mono float32。"""
    try:
        import fluidsynth
    except ImportError:
        return None
    data = json.load(open(json_path, encoding="utf-8"))
    events = json_to_events(data, bpm)
    if not events:
        return np.zeros(SAMPLE_RATE, dtype=np.float32)
    fs = fluidsynth.Synth(samplerate=SAMPLE_RATE, gain=gain)
    sfid = fs.sfload(sf_path)
    if sfid < 0:
        fs.delete()
        return None
    fs.program_select(0, sfid, 0, program)
    events.sort(key=lambda x: x[0])
    max_tick = max(t + d for t, _, d, _ in events)
    tps = 480 * bpm / 60.0
    total_sec = max_tick / tps + 1.0
    chunk_sec = 0.05
    chunk_samples = int(SAMPLE_RATE * chunk_sec)
    audio = []
    cur_sec = 0.0
    ev_idx = 0
    noteoff_queue = []
    while cur_sec < total_sec:
        chunk_end_tick = (cur_sec + chunk_sec) * tps
        while ev_idx < len(events) and events[ev_idx][0] <= chunk_end_tick:
            tick, mn, dur, vel = events[ev_idx]
            fs.noteon(0, mn, vel)
            noteoff_queue.append((tick + dur, mn))
            ev_idx += 1
        still = []
        for noff_tick, mn in noteoff_queue:
            if noff_tick <= chunk_end_tick:
                fs.noteoff(0, mn)
            else:
                still.append((noff_tick, mn))
        noteoff_queue = still
        audio.append(fs.get_samples(chunk_samples))
        cur_sec += chunk_sec
    for noff_tick, mn in noteoff_queue:
        fs.noteoff(0, mn)
    audio.append(fs.get_samples(int(SAMPLE_RATE * 0.5)))
    fs.delete()
    audio = np.concatenate(audio).astype(np.float32)
    if len(audio) % 2 == 0:
        audio = audio.reshape(-1, 2).mean(axis=1)
    if np.max(np.abs(audio)) > 1.5:
        audio = audio / 32768.0
    return audio


# ==================== 单轨音源解析 ====================
def resolve_track_source(name, cfg, track_dir):
    """返回 (audio_or_None, src_label, sr)。
    src_label: 'wav:<file>' / 'midi:<json>' / None(跳过)。"""
    source = cfg.get("source", "auto")
    wav_path = os.path.join(track_dir, name + ".wav")
    mid_path = os.path.join(track_dir, name + ".mid")
    json_path = os.path.join(track_dir, name + ".json")

    def try_wav():
        if os.path.exists(wav_path):
            audio, sr = load_wav_mono(wav_path)
            return audio, f"wav:{os.path.basename(wav_path)}", sr
        return None, None, None

    def try_midi():
        if not os.path.exists(mid_path) and not os.path.exists(json_path):
            return None, None, None
        sf_path = find_sf()
        if not sf_path:
            print(f"    [警告] 无 SoundFont，无法合成 midi: {name}")
            return None, None, None
        program = 0
        sf_pref = None
        if os.path.exists(json_path):
            try:
                tj = json.load(open(json_path, encoding="utf-8"))
                program = int(tj.get("program", 0))
                sf_pref = tj.get("soundfont")
            except Exception:
                pass
        sf_use = find_sf(sf_pref) or sf_path
        # 有 mid 文件直接渲染 mid；否则从 json 渲染
        if os.path.exists(mid_path):
            try:
                import fluidsynth, mido
                # 复用 render_midi_track 不读 mid，这里直接渲染 mid 文件
                return render_mid_file(mid_path, sf_use, program), f"midi:{os.path.basename(mid_path)}", SAMPLE_RATE
            except Exception as e:
                print(f"    [警告] midi 渲染失败 {name}: {e}")
        else:
            audio = render_midi_track(json_path, sf_use, program)
            if audio is not None:
                return audio, f"midi:{os.path.basename(json_path)}", SAMPLE_RATE
        return None, None, None

    if source == "wav":
        a, lbl, sr = try_wav()
        if a is None:
            print(f"    [警告] source=wav 但 {name}.wav 不存在，跳过")
        return a, lbl, sr
    if source == "midi":
        a, lbl, sr = try_midi()
        return a, lbl, sr
    # auto: wav 优先
    a, lbl, sr = try_wav()
    if a is not None:
        return a, lbl, sr
    return try_midi()


def render_mid_file(mid_path, sf_path, program, gain=2.5):
    """渲染独立 .mid 文件为 mono float32（复用 synth_full_song_fs 的 tick->sec 逻辑）。"""
    import fluidsynth, mido
    mid = mido.MidiFile(mid_path)
    tpb = mid.ticks_per_beat
    fs = fluidsynth.Synth(samplerate=SAMPLE_RATE, gain=gain)
    sfid = fs.sfload(sf_path)
    if sfid < 0:
        fs.delete()
        return None
    fs.program_select(0, sfid, 0, program)
    all_events = []
    for track in mid.tracks:
        ct = 0
        for msg in track:
            ct += msg.time
            all_events.append((ct, msg))
    all_events.sort(key=lambda x: x[0])
    max_tick = max(t[0] for t in all_events) if all_events else 0
    total_sec = 0.0; cur_tempo = 500000; prev_tick = 0
    for tick, msg in all_events:
        if msg.type == "set_tempo":
            total_sec += (tick - prev_tick) / tpb / (60_000_000 / cur_tempo) * 60
            prev_tick = tick; cur_tempo = msg.tempo
    total_sec += (max_tick - prev_tick) / tpb / (60_000_000 / cur_tempo) * 60
    total_sec += 1.0

    def tick_to_sec(target):
        s = 0.0; ct = 500000; pt = 0
        for tick, msg in all_events:
            if tick > target:
                break
            if msg.type == "set_tempo":
                s += (tick - pt) / tpb / (60_000_000 / ct) * 60
                pt = tick; ct = msg.tempo
        s += (target - pt) / tpb / (60_000_000 / ct) * 60
        return s

    chunk_sec = 0.05
    chunk_samples = int(SAMPLE_RATE * chunk_sec)
    audio = []; cur_sec = 0.0; ev_idx = 0
    while cur_sec < total_sec:
        chunk_end = cur_sec + chunk_sec
        while ev_idx < len(all_events):
            tick, msg = all_events[ev_idx]
            if tick_to_sec(tick) > chunk_end:
                break
            if msg.type == "program_change":
                try: fs.program_select(msg.channel, sfid, 0, msg.program)
                except Exception: pass
            elif msg.type == "note_on" and msg.velocity > 0:
                fs.noteon(msg.channel, msg.note, msg.velocity)
            elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                fs.noteoff(msg.channel, msg.note)
            elif msg.type == "control_change":
                fs.cc(msg.channel, msg.control, msg.value)
            ev_idx += 1
        audio.append(fs.get_samples(chunk_samples))
        cur_sec = chunk_end
    fs.delete()
    audio = np.concatenate(audio).astype(np.float32)
    if len(audio) % 2 == 0:
        audio = audio.reshape(-1, 2).mean(axis=1)
    # FluidSynth get_samples() 返回 int16 范围 [-32768, 32767]，归一化到 [-1, 1]
    if np.max(np.abs(audio)) > 1.5:
        audio = audio / 32768.0
    return audio


# ==================== 母带处理 ====================
def apply_pan(audio, pan):
    """pan: -1(左) ~ +1(右)，0 居中。返回立体声 (N,2)。"""
    if pan == 0:
        return np.stack([audio, audio], axis=1)
    lg = math.cos((pan + 1) * math.pi / 4)
    rg = math.sin((pan + 1) * math.pi / 4)
    return np.stack([audio * lg, audio * rg], axis=1)


def limiter(audio, ceiling=0.95):
    """硬限幅，防止削波。"""
    return np.clip(audio, -ceiling, ceiling)


def normalize(audio, target_peak=0.95):
    peak = np.max(np.abs(audio))
    if peak < 1e-6:
        return audio
    return audio / peak * target_peak


# ==================== remix.json 初始化 ====================
def init_remix_config(track_dir, project_name, bpm=68):
    """扫描 track 目录下所有 wav/mid，生成默认配置。"""
    tracks_cfg = {}
    seen = set()
    for fn in sorted(os.listdir(track_dir)):
        base, ext = os.path.splitext(fn)
        if ext.lower() not in (".wav", ".mid", ".json"):
            continue
        if base in seen:
            continue
        # 跳过 full 合成产物
        if base.startswith("full") or "_fs" in base or base.endswith("_toh") or base.endswith(".org"):
            continue
        seen.add(base)
        is_vocal = "主唱" in base or "vocal" in base.lower()
        tracks_cfg[base] = {
            "source": "auto",
            "vol": 1.0,
            "gain_db": 0.0,
            "mute": False,
            "pan": 0.0,
            "comment": "主唱轨，调 gain_db 放大/减小" if is_vocal else "",
        }
    cfg = {
        "schema": "remix.v1",
        "song": project_name,
        "bpm": bpm,
        "tracks": tracks_cfg,
        "master": {
            "normalize": True,
            "target_peak": 0.95,
            "limiter": True,
            "output": os.path.join(track_dir, "full_remix.wav").replace("\\", "/"),
        },
    }
    return cfg


# ==================== 主流程 ====================
def main():
    ap = argparse.ArgumentParser(description="remix-master：配置驱动音轨混音器")
    ap.add_argument("--project", default="走在", help="歌名（workspace/project/{歌名}）")
    ap.add_argument("--track-dir", default=None, help="音轨目录（默认 workspace/project/{歌名}/song_engineer/track）")
    ap.add_argument("--remix", default=None, help="remix.json 路径（默认 {track-dir}/../remix.json）")
    ap.add_argument("--init", action="store_true", help="扫描 track 目录生成默认 remix.json 后退出")
    ap.add_argument("--output", "-o", default=None, help="覆盖输出路径")
    args = ap.parse_args()

    track_dir = args.track_dir or os.path.join(
        "workspace", "project", args.project, "song_engineer", "track"
    )
    track_dir = os.path.abspath(track_dir)
    if not os.path.isdir(track_dir):
        print(f"[错误] track 目录不存在: {track_dir}"); sys.exit(1)

    remix_path = args.remix or os.path.join(os.path.dirname(track_dir), "remix.json")
    remix_path = os.path.abspath(remix_path)

    # --init：生成默认配置
    if args.init:
        cfg = init_remix_config(track_dir, args.project)
        with open(remix_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        print(f"[初始化] 已生成默认 remix.json: {remix_path}")
        print(f"  扫描到 {len(cfg['tracks'])} 条轨。编辑各轨 gain_db/vol 后重跑（去掉 --init）即可混音。")
        return

    # 读 remix.json
    if not os.path.exists(remix_path):
        print(f"[错误] remix.json 不存在: {remix_path}")
        print(f"  先跑: {sys.argv[0]} --project {args.project} --init")
        sys.exit(1)
    try:
        cfg = json.load(open(remix_path, encoding="utf-8"))
    except Exception as e:
        print(f"[错误] remix.json 解析失败: {e}"); sys.exit(1)

    if not cfg.get("tracks"):
        print(f"[提示] remix.json 为空或无 tracks，自动生成默认配置并写回...")
        cfg = init_remix_config(track_dir, args.project)
        with open(remix_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        print(f"  已写回 {remix_path}（{len(cfg['tracks'])} 条轨）。编辑后重跑。")
        return

    master = cfg.get("master", {})
    bpm = cfg.get("bpm", 68)
    out_path = args.output or master.get("output") or os.path.join(track_dir, "full_remix.wav")
    target_peak = master.get("target_peak", 0.95)
    do_norm = master.get("normalize", True)
    do_lim = master.get("limiter", True)

    print(f"[混音] 项目={args.project} BPM={bpm} 轨数={len(cfg['tracks'])}")
    print(f"  remix.json: {remix_path}")
    print(f"  输出: {out_path}")
    print()

    # 逐轨解析
    track_audios = []  # [(name, stereo_audio, src_label, cfg)]
    for name, tcfg in cfg["tracks"].items():
        if tcfg.get("mute", False):
            print(f"  [静音] {name}  (mute=true)")
            continue
        audio, src_label, sr = resolve_track_source(name, tcfg, track_dir)
        if audio is None or len(audio) == 0:
            print(f"  [跳过] {name}  (无可用音源 wav/mid)")
            continue
        if sr != SAMPLE_RATE:
            from scipy.interpolate import interp1d
            x_old = np.linspace(0, 1, len(audio))
            x_new = np.linspace(0, 1, int(len(audio) * SAMPLE_RATE / sr))
            audio = interp1d(x_old, audio, kind="linear")(x_new).astype(np.float32)

        vol = float(tcfg.get("vol", 1.0))
        gain_db = float(tcfg.get("gain_db", 0.0))
        amp = vol * (10 ** (gain_db / 20.0))
        pan = float(tcfg.get("pan", 0.0))
        audio = audio * amp
        stereo = apply_pan(audio, pan)
        peak = np.max(np.abs(stereo))
        rms = float(np.sqrt(np.mean(stereo ** 2)))
        track_audios.append((name, stereo, src_label, tcfg))
        print(f"  [混入] {name:14s} {src_label:34s} amp={amp:.3f} (vol={vol:.2f} gain={gain_db:+.1f}dB) "
              f"len={len(stereo)/SAMPLE_RATE:.1f}s peak={peak:.3f} rms={rms:.4f}")

    if not track_audios:
        print("\n[错误] 无可混入音轨"); sys.exit(1)

    # 对齐到最长轨
    L = max(a.shape[0] for _, a, _, _ in track_audios)
    mix = np.zeros((L, 2), dtype=np.float32)
    print(f"\n[叠加] 基准长度 {L/SAMPLE_RATE:.1f}s，叠加 {len(track_audios)} 轨")
    for name, audio, src, _ in track_audios:
        mix[:audio.shape[0]] += audio

    pre_peak = np.max(np.abs(mix))
    print(f"  叠加后峰值: {pre_peak:.3f}")

    # 母带
    if do_lim:
        mix = limiter(mix, ceiling=1.0)
    if do_norm:
        mix = normalize(mix, target_peak)
    final_peak = np.max(np.abs(mix))
    print(f"  母带后峰值: {final_peak:.3f} (target={target_peak})")

    # 写文件（先 tmp ASCII 路径再 copy，规避中文路径 libsndfile 偶发错误）
    tmp_path = os.path.join(tempfile.gettempdir(), f"__remix_{os.getpid()}.wav")
    try:
        sf.write(tmp_path, mix.astype(np.float32), SAMPLE_RATE, subtype="PCM_16")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        if os.path.exists(out_path):
            os.remove(out_path)
        shutil.copy(tmp_path, out_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    print(f"\n[完成] {out_path}")
    print(f"  时长: {mix.shape[0]/SAMPLE_RATE:.1f}s | 峰值: {final_peak:.3f} | 轨数: {len(track_audios)}")
    # 关键提示：主唱用的是不是真实干声
    for name, _, src, _ in track_audios:
        if "主唱" in name or "vocal" in name.lower():
            print(f"  ★ 主唱音源: {src}  ({'[OK] 真实干声  改 gain_db 立即生效' if src.startswith('wav') else '[!!] MIDI 合成（非真实人声）'})")


if __name__ == "__main__":
    main()
