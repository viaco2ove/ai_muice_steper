# -*- coding: utf-8 -*-
"""
synth_multitrack_fs.py - FluidSynth 多轨合成(10轨叠加)

读各轨 json -> 各自导出 MIDI -> FluidSynth 合成 -> 叠加输出全曲 wav。
支持吉他×4 + 主唱 + 和声 + 环境音×4 = 10轨。

音量平衡 + 音色(program)按轨配置。
"""
import os
import sys
import json
import argparse
import numpy as np
import soundfile as sf

# 读 .env
_env = {}
_cur = os.path.dirname(os.path.abspath(__file__))
for _ in range(5):
    _c = os.path.join(_cur, ".env")
    if os.path.exists(_c):
        with open(_c, encoding="utf-8") as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    _env[k] = v
        break
    _cur = os.path.dirname(_cur)
FS_PATH = _env.get("fluidsynth_path", "")
SF_DIR = _env.get("soundfonts_path", "")
os.environ["PATH"] = os.path.join(FS_PATH, "bin") + ";" + os.environ["PATH"]

import fluidsynth
import mido

SAMPLE_RATE = 44100
CHUNK_SEC = 0.05

# 10轨配置:(json文件名, SF文件名, program, 音量)
# SF 绑定:按各SF特长分配(人声FluidR3突出,吉他GeneralUser/SGM,爵士Arachno,pad Timbres)
TRACKS = [
    ("01_吉他",            "GeneralUser GS v1.471.sf2", 25, 0.6),   # 钢弦吉他分解
    ("02_主唱",            "FluidR3_GM2-2.SF2",         54, 1.0),   # Human Voice 真人基础人声
    ("09_和声",            "Arachno_SoundFont_Version_1.0.sf2", 85, 0.4),  # Voice Oohs program 85 (与主唱 Synth Voice 54 区分)
    ("05_solo吉他主",      "SGM-V2.01.sf2",             25, 0.8),   # 钢弦温暖
    ("06_solo吉他辅1",     "GeneralUser GS v1.471.sf2", 24, 0.5),   # 尼龙
    ("07_solo吉他辅2",     "Arachno_SoundFont_Version_1.0.sf2", 26, 0.5),  # 爵士
    ("08_节奏吉他",        "SGM-V2.01.sf2",             25, 0.65),  # 钢弦
    ("10_氛围垫音pad",     "Timbres Of Heaven GM_GS_XG_SFX V 3.4 Final.sf2", 88, 0.3),  # pad
    ("12_泛音环境点缀",    "GeneralUser GS v1.471.sf2", 25, 0.4),   # 泛音
    ("13_轻贝斯",          "FluidR3_GM2-2.SF2",         33, 0.5),   # 贝斯
    # 11_自然白噪音 跳过(midi=0 无音高,SF 无法合成白噪)
]


def find_sf(preferred=None):
    """查找 SF,优先用指定的"""
    if preferred:
        p = os.path.join(SF_DIR, preferred)
        if os.path.exists(p):
            return p
    # fallback:GeneralUser
    if os.path.isdir(SF_DIR):
        for f in sorted(os.listdir(SF_DIR)):
            if "GeneralUser" in f and f.lower().endswith((".sf2", ".sf3")):
                return os.path.join(SF_DIR, f)
    return None


# 复用 export_track_to_midi 的导出逻辑(内联精简版,支持 bars/melody_note_level/notes 三种)
NOTE2MIDI = {"C":0,"C#":1,"D":2,"D#":3,"E":4,"F":5,"F#":6,"G":7,"G#":8,"A":9,"A#":10,"B":11}
DUR2TICKS = {"16分":120,"8分":240,"4分":480,"2分":960,"全分":480,"全延":480,"":240}
DYN2VEL = {"ppp":25,"pp":45,"p":60,"mp":75,"mf":85,"f":95,"ff":105,"fff":115}

def note_to_midi(name):
    import re
    if not name or name.strip() in ("","留白","slap","noise"): return None
    name = name.replace("泛音","").strip()
    m = re.match(r"([A-G])([#b]?)(-?\d+)", name)
    if not m: return None
    letter, accidental, octave = m.group(1), m.group(2), m.group(3)
    base = {"C":0,"D":2,"E":4,"F":5,"G":7,"A":9,"B":11}[letter]
    if accidental == "#": base += 1
    elif accidental == "b": base -= 1
    return base + (int(octave) + 1) * 12

def bar_offset(bar, beat, frac):
    return (bar-1)*4*480 + (beat-1)*480 + (frac-1)*240

def json_to_events(data):
    """从 json 提取 (tick, midi, dur_tick, vel) 事件列表"""
    events = []
    # bars
    for i, bar in enumerate(data.get("bars", [])):
        for b in bar.get("beats", []):
            mn = note_to_midi(b.get("actual") or b.get("note") or "")
            if mn is None: continue
            pos = b.get("pos","1.1").split(".")
            try: beat, frac = int(pos[0]), int(pos[1]) if len(pos)>1 else 1
            except: continue
            tick = bar_offset(i+1, beat, frac)
            dur = DUR2TICKS.get(b.get("dur","4分"), 480)
            vel = DYN2VEL.get(b.get("dynamics","p"), 60)
            events.append((tick, mn, dur, vel))
    # melody_note_level
    m = data.get("melody_note_level")
    if m:
        for notes in m.get("sections", {}).values():
            for n in notes:
                mn = n.get("midi")
                if mn is None or mn < 0: continue
                bp = n.get("beat_pos","1.1.1").split(".")
                try:
                    bar = int(bp[0]); beat = int(bp[1]) if len(bp)>1 else 1
                    fs = bp[2] if len(bp)>2 else "1"
                    if fs=="末": beat=min(beat+1,4); frac=1
                    else: frac=int(fs)
                except: continue
                tick = bar_offset(bar, beat, frac)
                dur = DUR2TICKS.get(n.get("duration","8分"), 240)
                vel = n.get("velocity", 60)
                if isinstance(vel, str): vel = DYN2VEL.get(vel, 60)
                events.append((tick, mn, dur, int(vel)))
    # notes 扁平
    for n in data.get("notes", []):
        if not isinstance(n, dict):
            continue  # 跳过非音符(如备注字符串)
        nn = n.get("actual") or n.get("note") or ""
        if nn in ("slap","noise") or n.get("midi",-1)==0: continue
        mn = note_to_midi(nn)
        if mn is None:
            # 直接用 midi 字段
            mn = n.get("midi")
            if mn is None or mn <= 0: continue
        bp = n.get("beat_pos","1.1.1").split(".")
        try:
            bar = int(bp[0]); beat = int(bp[1]) if len(bp)>1 else 1
            fs = bp[2] if len(bp)>2 else "1"
            if fs=="末": beat=min(beat+1,4); frac=1
            else: frac=int(fs)
        except: continue
        tick = bar_offset(bar, beat, frac)
        dur = DUR2TICKS.get(n.get("duration","4分"), 480)
        vel = n.get("velocity", 60)
        if isinstance(vel, str): vel = DYN2VEL.get(vel, 60)
        events.append((tick, mn, dur, int(vel)))
    return events


def render_track_json(json_path, sf_path, program, gain=2.5):
    """读 json -> 事件 -> FluidSynth 渲染 -> mono float32

    FluidSynth get_samples() 在 -32768~32767 整数范围,归一化后实际信号在 ±0.5,
    故 gain=2.5 让单轨峰值接近 ±1 留 headroom,后期混音有空间处理。"""
    data = json.load(open(json_path, encoding="utf-8"))
    events = json_to_events(data)
    if not events:
        return np.zeros(SAMPLE_RATE), 0

    fs = fluidsynth.Synth(samplerate=SAMPLE_RATE, gain=gain)
    sfid = fs.sfload(sf_path)
    fs.program_select(0, sfid, 0, program)

    events.sort(key=lambda x: x[0])
    max_tick = max(t + d for t, _, d, _ in events)
    tps = 480 * 68 / 60  # ticks per sec (BPM68)
    total_sec = max_tick / tps + 1.0
    chunk_samples = int(SAMPLE_RATE * CHUNK_SEC)

    audio = []
    cur_sec = 0
    ev_idx = 0
    # noteoff 队列:(noteoff_tick, midi_num)
    noteoff_queue = []
    while cur_sec < total_sec:
        chunk_end_tick = (cur_sec + CHUNK_SEC) * tps
        # 触发该 chunk 内的 noteon
        while ev_idx < len(events) and events[ev_idx][0] <= chunk_end_tick:
            tick, mn, dur, vel = events[ev_idx]
            fs.noteon(0, mn, vel)
            noteoff_queue.append((tick + dur, mn))
            ev_idx += 1
        # 触发该 chunk 内该 noteoff 的
        still = []
        for noff_tick, mn in noteoff_queue:
            if noff_tick <= chunk_end_tick:
                fs.noteoff(0, mn)
            else:
                still.append((noff_tick, mn))
        noteoff_queue = still
        samples = fs.get_samples(chunk_samples)
        audio.append(samples)
        cur_sec += CHUNK_SEC

    # 收尾:触发剩余 noteoff
    for noff_tick, mn in noteoff_queue:
        fs.noteoff(0, mn)
    # 再渲染 0.5s 让尾音衰减
    audio.append(fs.get_samples(int(SAMPLE_RATE * 0.5)))

    audio = np.concatenate(audio).astype(np.float32)
    if len(audio) % 2 == 0:
        audio = audio.reshape(-1, 2).mean(axis=1)
    # FluidSynth get_samples() 返回 int16 范围 [-32768, 32767],需归一化到 [-1, 1]
    if np.max(np.abs(audio)) > 1.5:  # 检测整数范围
        audio = audio / 32768.0
    fs.delete()
    return audio, len(events)


def main():
    ap = argparse.ArgumentParser(description="FluidSynth 10轨合成全曲(支持 wav 注入)")
    ap.add_argument("--trackdir", default="workspace/project/走在/song_engineer/track")
    ap.add_argument("-o", "--output", default="workspace/project/走在/song_engineer/track/full_multitrack_fs.wav")
    args = ap.parse_args()

    sf_default = find_sf()
    if not sf_default:
        print("[错误] 未找到 SoundFont"); sys.exit(1)
    print("默认 SF:", os.path.basename(sf_default))

    all_audio = []
    # wav 注入轨(不走 FluidSynth,直接读 wav 文件按音量混入)
    WAV_INJECT = [
        ("11_自然白噪音", 0.4),  # 雨声/风声/远处声
    ]
    for fname, vol in WAV_INJECT:
        wp = os.path.join(args.trackdir, fname + ".wav")
        if not os.path.exists(wp):
            print(f"  [跳过] {fname}.wav 不存在")
            continue
        wav_data, sr = sf.read(wp, dtype="float32")
        if wav_data.ndim > 1:
            wav_data = wav_data.mean(axis=1)
        if sr != SAMPLE_RATE:
            # 简易重采样:线性插值
            from scipy.interpolate import interp1d
            x_old = np.linspace(0, 1, len(wav_data))
            x_new = np.linspace(0, 1, int(len(wav_data) * SAMPLE_RATE / sr))
            wav_data = interp1d(x_old, wav_data, kind="linear")(x_new).astype(np.float32)
        print(f"[注入] {fname} (wav={os.path.basename(wp)}, vol={vol}, {len(wav_data)/SAMPLE_RATE:.1f}s)")
        all_audio.append((wav_data * vol, fname))

    # FluidSynth 渲染轨
    for fname, sf_name, program, vol in TRACKS:
        jp = os.path.join(args.trackdir, fname + ".json")
        if not os.path.exists(jp):
            print(f"  [跳过] {fname}.json 不存在")
            continue
        sf_path = find_sf(sf_name) or sf_default
        print(f"[渲染] {fname} (SF={os.path.basename(sf_path)[:20]}, program={program}, vol={vol})")
        audio, n = render_track_json(jp, sf_path, program)
        print(f"  {n}音 -> {len(audio)/SAMPLE_RATE:.1f}s")
        all_audio.append((audio * vol, fname))

    if not all_audio:
        print("[错误] 无可渲染轨"); sys.exit(1)

    L = max(len(a) for a, _ in all_audio)
    mix = np.zeros(L)
    for audio, name in all_audio:
        mix[:len(audio)] += audio

    peak = np.max(np.abs(mix))
    if peak > 0.85:
        mix = mix / peak * 0.85
    elif peak < 0.1:
        mix = mix / max(peak, 1e-6) * 0.5  # 太轻时拉到 0.5
    # Windows 长 wav+中文路径下偶发 LibsndfileError,先写 ASCII 临时路径,再 shutil.copy 到目标
    import tempfile, shutil
    tmp_dir = tempfile.gettempdir()
    tmp_path = os.path.join(tmp_dir, f"__mix_{os.getpid()}.wav")
    try:
        sf.write(tmp_path, mix.astype(np.float32), SAMPLE_RATE, subtype="PCM_16")
        if os.path.exists(args.output):
            os.remove(args.output)
        shutil.copy(tmp_path, args.output)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    print(f"\n[输出] {args.output}")
    print(f"  时长: {len(mix)/SAMPLE_RATE:.1f}s | 峰值: {peak:.3f} | 轨数: {len(all_audio)}")
    print(f"  SF: {os.path.basename(sf_path)}")


if __name__ == "__main__":
    main()