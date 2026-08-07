# -*- coding: utf-8 -*-
"""DiffSinger 渲染器 CLI (ds/ 包, 配置驱动, 复刻 OpenUTAU 官方输入契约)

用法:
  python render_singer.py --project 走在 --track 02_主唱 --bpm 68     # plan+render 全流程
  python render_singer.py --project 走在 --track 02_主唱 --plan-only  # 只生成 ustx.json
  python render_singer.py --project 走在 --track 02_主唱 --from-plan  # 从已有 ustx.json 渲染
  python render_singer.py ... --steps 20 --steps-pitch 10 --steps-variance 20
声库由 .env 的 singers_path 推导 (ds/voicebank.py locate)。
"""
import argparse
import json
import os
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ds.voicebank import Voicebank, HEAD_FRAMES, TAIL_FRAMES
from ds.align import read_midi_notes, align_lyrics_linear, BAR_SEGS
from ds.plan import PlanBuilder
from ds.render import Renderer, write_audio


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--track", default="02_主唱")
    ap.add_argument("--lyrics-json", default=None)
    ap.add_argument("--bpm", type=float, default=68.0)
    ap.add_argument("--out", default=None, help="输出wav路径(默认 track/singer/{track}.wav)")
    ap.add_argument("--plan", dest="plan_path", default=None,
                    help="ustx.json路径(默认 track/singer/{track}.ustx.json)")
    ap.add_argument("--plan-only", action="store_true", help="只生成plan, 不渲染")
    ap.add_argument("--from-plan", action="store_true", help="跳过plan生成, 从已有plan渲染")
    ap.add_argument("--steps", type=int, default=20, help="acoustic扩散步数(官方默认20)")
    ap.add_argument("--steps-pitch", type=int, default=10, help="pitch扩散步数(官方默认10)")
    ap.add_argument("--steps-variance", type=int, default=20, help="variance扩散步数(官方默认20)")
    args = ap.parse_args()

    proj = os.path.join("workspace", "project", args.project)
    singer = os.path.join(proj, "song_engineer", "track", "singer")
    os.makedirs(singer, exist_ok=True)
    plan_path = args.plan_path or os.path.join(singer, args.track + ".ustx.json")

    vb = Voicebank(Voicebank.locate())
    sess = vb.sessions()
    print("voicebank: %s" % vb.root)

    if args.from_plan:
        with open(plan_path, encoding="utf-8") as f:
            plan = json.load(f)
        print("plan loaded: %s (notes=%d)" % (plan_path, len(plan["notes"])))
    else:
        lj = args.lyrics_json or os.path.join(proj, "song_engineer", "track", "03_lyrics.json")
        with open(lj, encoding="utf-8") as f:
            ldata = json.load(f)
        mp = os.path.join(proj, "song_engineer", "track", args.track + ".mid")
        midi_n, tpb = read_midi_notes(mp)
        lyrics = align_lyrics_linear(midi_n, ldata.get("lyric_sections", []), BAR_SEGS, tpb)
        print("notes=%d chars=%d slur(-)=%d rest=%d" % (
            len(midi_n), sum(1 for l in lyrics if l not in ("R", "-")),
            lyrics.count("-"), lyrics.count("R")))
        with open(os.path.join(singer, "lyrics_match_v6.json"), "w", encoding="utf-8") as f:
            json.dump({"midi_notes": midi_n, "lyrics": lyrics,
                       "bpm": args.bpm, "tpb": tpb}, f, ensure_ascii=False)

        meta = {
            "name": args.track, "project": args.project,
            "bpm": args.bpm, "tpb": tpb, "fps": vb.cfg_ac.fps,
            "sample_rate": int(vb.cfg_voc.sample_rate), "hop_size": int(vb.cfg_voc.hop_size),
            "head_frames": HEAD_FRAMES, "tail_frames": TAIL_FRAMES,
            "singer": (vb.cfg_ac.speakers or ["?"])[0], "voicebank": vb.root,
            "models": {
                "ling_dur": vb.cfg_dur.path(vb.cfg_dur.linguistic),
                "dur": vb.cfg_dur.path(vb.cfg_dur.dur),
                "ling_var": vb.cfg_var.path(vb.cfg_var.linguistic),
                "variance": vb.cfg_var.path(vb.cfg_var.variance),
                "ling_pitch": vb.cfg_pitch.path(vb.cfg_pitch.linguistic),
                "pitch": vb.cfg_pitch.path(vb.cfg_pitch.pitch),
                "acoustic": vb.cfg_ac.path(vb.cfg_ac.acoustic),
                "vocoder": vb.cfg_voc.path(vb.cfg_voc.model),
            },
            "bar_segs": BAR_SEGS,
            "sources": {"mid": mp, "lyrics": lj},
            "generator": "ds/ package (OpenUTAU official input contract)",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        print("building plan (align+segment+phoneme+dur bake)...")
        plan = PlanBuilder(vb, sess).build(midi_n, lyrics, args.bpm, tpb, meta)
        with open(plan_path, "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=1)
        print("plan saved: %s (notes=%d)" % (plan_path, len(plan["notes"])))
        if args.plan_only:
            return

    print("synthesizing (pitch->variance->acoustic->vocoder, from plan)...")
    r = Renderer(vb, sess, args.steps, args.steps_pitch, args.steps_variance)
    audio = r.synth_from_plan(plan)

    m = plan["meta"]
    sr = int(m.get("sample_rate", 44100))
    dur = len(audio) / float(r.sr)
    last = plan["notes"][-1]
    midi_dur = (last["position"] + last["duration"]) / (m["tpb"] * m["bpm"] / 60.0)
    print("output: %.1fs (MIDI全长%.1fs, 漂移%+.2f%%)" % (
        dur, midi_dur, 100 * (dur - midi_dur) / midi_dur))

    out = args.out or os.path.join(singer, args.track + ".wav")
    write_audio(audio, out, sr, r.sr)
    print("saved: %s" % out)


if __name__ == "__main__":
    main()
